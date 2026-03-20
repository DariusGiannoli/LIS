/* Vibration_Unit.c — PIC16F18313 @ 32 MHz (XC8 v3.10, -O0)
 * Proto: Addr (MSB=0) → Data1 duty5 (MSB=1) → Data2 (MSB=1) = [1 0 0 W F2 F1 F0]
 * wave=1 : TRUE-SINE (Timer1 + LUT 64 signée, PWM ~40kHz fixe via Timer2, routage PPS RA0/RA1)
 * wave=0 : SQUARE (CWG + fenêtrage)
 */

#include <xc.h>
#include <stdint.h>
#include "neopixel_control.h"   // définit _XTAL_FREQ=32000000, SPI_Init(), sendColor_SPI()

// ==================== Config Bits ====================
// MCLRE=OFF : CRITIQUE pour éviter le flottement des broches au démarrage sur batterie
#pragma config FEXTOSC=OFF, RSTOSC=HFINT32, CLKOUTEN=OFF, CSWEN=OFF, FCMEN=OFF
#pragma config MCLRE=OFF, PWRTE=ON, WDTE=OFF, LPBOREN=OFF, BOREN=OFF, BORV=LOW, PPS1WAY=OFF, STVREN=ON, DEBUG=OFF
#pragma config WRT=OFF, LVP=OFF, CP=OFF, CPD=OFF

// ==================== Etat / Protocole ====================
static volatile uint8_t buffer = 0;
static volatile uint8_t state  = 0;     // 0:addr, 1:duty, 2:wave+freq
static volatile uint8_t wave_mode  = 1; // 1=sine, 0=square
static volatile uint8_t duty5_raw  = 0; // 0..31
static volatile uint8_t duty_pct   = 0; // 0..99
static volatile uint8_t freq_index = 3; // 0..7
static volatile uint8_t uart_led_flag = 0;

// ==================== LED ====================
static uint8_t color_index = 0;
static uint8_t color[3]    = {0,0,0};
static const uint8_t KEY16[16][3] = {
  {  0,  0,  0},  {  0, 32, 32},  {  0, 64, 64},  {  0,128,128},
  {  0,255,255},  {  0,255,128},  {  0,255,  0},  {128,255,  0},
  {255,255,  0},  {255,128,  0},  {255,  0,  0},  {255,  0,128},
  {255,  0,255},  {128,  0,255},  { 64,  0,255},  {255,255,255}
};
static inline void getColor32(uint8_t idx32, uint8_t out[3]){
    if(idx32 > 31) idx32 = 31;
    uint8_t seg = idx32 >> 1, odd = idx32 & 1;
    if(!odd || seg >= 15){
        out[0]=KEY16[seg][0]; out[1]=KEY16[seg][1]; out[2]=KEY16[seg][2];
    }else{
        out[0]=(uint8_t)((KEY16[seg][0]+KEY16[seg+1][0])>>1);
        out[1]=(uint8_t)((KEY16[seg][1]+KEY16[seg+1][1])>>1);
        out[2]=(uint8_t)((KEY16[seg][2]+KEY16[seg+1][2])>>1);
    }
}

// ==================== PWM (Timer2 / CCP1) ====================
static inline void set_pwm10(uint16_t dc10){
    CCPR1H = (uint8_t)(dc10 >> 2);
    CCPR1L = (uint8_t)((dc10 & 0x3u) << 6);
}

// ==================== TRUE-SINE (Timer1 + LUT signée 64) ====================
#define SINE_LEN 64u
#define CCP1_PPS_CODE 0x0C   // code PPS pour assigner CCP1 sur RA0/RA1
#define MIN_DRIVE_TKS 2u

static const int8_t SINE64_8[SINE_LEN] = {
     0,  12,  25,  37,  49,  60,  71,  81,
    90,  99, 106, 113, 118, 122, 125, 127,
   127, 127, 125, 122, 118, 113, 106,  99,
    90,  81,  71,  60,  49,  37,  25,  12,
     0, -12, -25, -37, -49, -60, -71, -81,
   -90, -99,-106,-113,-118,-122,-125,-127,
  -127,-127,-125,-122,-118,-113,-106, -99,
   -90, -81, -71, -60, -49, -37, -25, -12
};

// Fondamentales (Hz) et reloads Timer1 (tick = 1 µs, 64 échan.)
static const uint16_t FREQ_HZ[8]   = {123,145,170,200,235,275,322,384};
static const uint16_t T1_RELOAD[8] = {
    (uint16_t)(65536u - 127u),
    (uint16_t)(65536u - 108u),
    (uint16_t)(65536u -  92u),
    (uint16_t)(65536u -  78u),
    (uint16_t)(65536u -  66u),
    (uint16_t)(65536u -  57u),
    (uint16_t)(65536u -  49u),
    (uint16_t)(65536u -  41u)
};

static volatile uint8_t  phase_idx = 0;
static volatile int8_t   last_sign = 0;
static volatile uint16_t t1_reload = 0;
static volatile uint16_t scale     = 0;  // 0..top

// détacher CCP1 des pins & mettre RA0/RA1 à 0 (Sécurité absolue)
static inline void coast_both(void){
    RA1PPS = 0; LATAbits.LATA1 = 0;
    RA0PPS = 0; LATAbits.LATA0 = 0;
}

// route demi-cycle: + → RA1=1 et PWM sur RA0 ; − → RA0=1 et PWM sur RA1
static inline void route_halfcycle(int8_t sign){
    if (sign > 0){
        RA0PPS = CCP1_PPS_CODE;  // PWM sur RA0
        RA1PPS = 0;
        LATAbits.LATA1 = 1; LATAbits.LATA0 = 0;
    } else {
        RA1PPS = CCP1_PPS_CODE;  // PWM sur RA1
        RA0PPS = 0;
        LATAbits.LATA0 = 1; LATAbits.LATA1 = 0;
    }
}

static inline void t1_apply_reload(uint8_t fidx){
    t1_reload = T1_RELOAD[fidx & 0x7u];
    T1CONbits.TMR1ON = 0;
    TMR1H = (uint8_t)(t1_reload >> 8);
    TMR1L = (uint8_t)(t1_reload & 0xFF);
    PIR1bits.TMR1IF = 0;
    T1CONbits.TMR1ON = 1;
}

// fixe l’amplitude 0..99 % → échelle 10 bits (top = 4*(PR2+1)-1)
static inline void lra_set_amp(uint8_t pct){
    if (pct > 100) pct = 100;
    uint16_t top = (uint16_t)(4u * ((uint16_t)PR2 + 1u) - 1u); // PR2=199 → top=799
    scale = (uint16_t)(((uint32_t)top * (uint32_t)pct + 50u) / 100u);
    if (!scale){ coast_both(); set_pwm10(0); }
}

// ==================== SQUARE (CWG + fenêtrage) ====================
static const uint8_t PR_val[8] = {85,72,60,52,44,37,32,27};
static volatile uint8_t index200 = 0;
static volatile uint8_t cwg_flag  = 0;
static volatile uint8_t duty_flag = 0;
static volatile uint8_t square_tick = 0;   // flag main-loop

static void square_processing(void){
    uint8_t on = (index200 < duty_pct) ||
                 (index200 >= 100 && index200 < (uint8_t)(100 + duty_pct));

    if (on){
        uint8_t half = (index200 >= 100);
        if (cwg_flag == 0 || (last_sign != (half ? -1 : +1))){
            CWG1CON0bits.EN = 0;
            if (!half){ CWG1CON1bits.POLA = 0; CWG1CON1bits.POLB = 0; last_sign = +1; }
            else       { CWG1CON1bits.POLA = 1; CWG1CON1bits.POLB = 1; last_sign = -1; }
            CWG1CON0bits.EN = 1;
            cwg_flag = 1;
        }
        if (duty_flag == 0){
            uint16_t top = (uint16_t)(4u * ((uint16_t)PR2 + 1u) - 1u);
            set_pwm10(top);
            duty_flag = 1;
        }
    }else{
        if (cwg_flag == 1){
            CWG1CON0bits.EN = 0;
            CWG1CON1bits.POLA = 0;
            CWG1CON1bits.POLB = 1; // sorties identiques → annule la diff
            CWG1CON0bits.EN = 1;
            cwg_flag = 0;
        }
        if (duty_flag == 1){
            set_pwm10(0);
            duty_flag = 0;
        }
    }
}

// ==================== UART ====================
static inline uint8_t make_addr_byte(uint8_t start, uint8_t addr6){
    return (uint8_t)((addr6 & 0x3Fu) << 1) | (start & 1u);
}
static inline void UART_Write(uint8_t d){ while(!TRMT){} TX1REG = d; }

static void UART_processing(void){
    if ((buffer >> 7) == 0){
        // ADDR
        uint8_t addr  = (buffer >> 1) & 0x3F;
        uint8_t start = (buffer & 1u);
        if (addr != 0){
            --addr; UART_Write(make_addr_byte(start, addr));
            state = 0; return;
        }else{
            if (!start){
                // ================= STOP =================
                T1CONbits.TMR1ON = 0; PIE1bits.TMR1IE = 0;
                
                // Verrouillage physique à 0V (GND)
                coast_both(); 
                set_pwm10(0);

                T2CONbits.TMR2ON = 0; TMR2IE = 0;
                
                // CWG OFF et Pins non connectées (Sécurité chauffe)
                CWG1CON0bits.EN = 0; 
                
                duty_pct = 0; cwg_flag = 0; duty_flag = 0; square_tick = 0;
                state = 0;
            }else{
                state = 1; // attendre duty
            }
            return;
        }
    }else{
        // DATA
        if (state == 0){
            UART_Write(buffer); return;
        }else if (state == 1){
            duty5_raw = (uint8_t)(buffer & 0x1Fu); // 0..31
            state = 2; return;
        }else{
            uint8_t d2 = buffer & 0x7Fu;
            wave_mode  = (d2 >> 3) & 0x01u;
            freq_index = d2 & 0x07u;

            // ===== NOUVEAU CALCUL (FULL POWER + START BOOST) =====
            if (duty5_raw == 0) {
                duty_pct = 0;
            } else {
                // On mappe l'entrée 1..31 vers la sortie 15%..100%
                // Formule : Base + (Raw * Ecart / Max)
                // Cela permet de sentir la vibration dès le niveau 1
                // Et d'aller à 100% au niveau 31 pour SINE et SQUARE.
                
                // 15 + (duty5_raw * 85 / 32)
                duty_pct = 15 + (uint8_t)(((uint16_t)duty5_raw * 85u) / 32u);
                
                // Sécurité capuchon à 100%
                if (duty_pct > 100) duty_pct = 100;
            }

            uart_led_flag = 1;

            if (wave_mode){
                // ===== TRUE-SINE =====
                T2CONbits.TMR2ON = 0;
                T2CONbits.T2CKPS = 0b00; // 1:1
                PR2 = 199; set_pwm10(0);
                TMR2 = 0; TMR2IF = 0; T2CONbits.TMR2ON = 1;

                CCP1CON = 0b10011111; 

                CWG1CON0bits.EN = 0; 
                coast_both();        

                T1CON = 0;
                T1CONbits.T1CKPS = 0b11; 
                PIR1bits.TMR1IF = 0; PIE1bits.TMR1IE = 1;
                phase_idx = 0; last_sign = 0;
                lra_set_amp(duty_pct);
                t1_apply_reload(freq_index);
            }else{
                // ===== SQUARE =====
                T1CONbits.TMR1ON = 0; PIE1bits.TMR1IE = 0;
                coast_both();   

                CCP1CON = 0b10011111;

                RA1PPS = 0b01000; RA0PPS = 0b01001; 
                CWG1CON0bits.EN = 1; 

                T2CONbits.TMR2ON = 0;
                T2CONbits.T2CKPS = 0b01; // 1:4
                PR2 = PR_val[freq_index];
                TMR2 = 0; TMR2IF = 0; T2CONbits.TMR2ON = 1; TMR2IE = 1;

                index200 = 0; cwg_flag = 0; duty_flag = 0; square_tick = 0; last_sign = 0;
            }
            state = 0; return;
        }
    }
}

// ==================== Init ====================
static void usart_init(void){
    TRISA5 = 1; TRISA2 = 1; ANSELA = 0;
    RXPPS  = 0b00101;      // RA5 -> RX
    RA2PPS = 0b10100;      // TX  -> RA2
    RC1STA   = 0b10010000; // SPEN=1, CREN=1
    TX1STA   = 0b00100100; // BRGH=1, TXEN=1
    BAUD1CON = 0b00001000; // BRG16=1
    SP1BRGH  = 0; SP1BRGL = 68; // 115200 @32MHz
    RCIF=0; RCIE=1;
    __delay_us(100);
}

static void pwm_cwg_init(void){
    ANSELA = 0;
    TRISAbits.TRISA0 = 0;
    TRISAbits.TRISA1 = 0;

    // CCP1 PWM, format right-aligned
    CCP1CON = 0b10011111;
    set_pwm10(0);

    // Timer2
    T2CON = 0;
    T2CONbits.T2CKPS = 0b00;
    PR2 = 199; TMR2 = 0; TMR2IF = 0; T2CONbits.TMR2ON = 1;

    // CWG init (mais non connecté aux pins)
    CWG1CLKCON = 1; CWG1DAT = 0b00000011; // source = CCP1
    CWG1CON1 = 0; CWG1AS0 = 0b01111000;
    CWG1DBR = 0; CWG1DBF = 0;
    
    // --- SECURITE INIT ---
    CWG1CON0 = 0b01000100; 
    CWG1CON0bits.EN = 0;   // START A 0 (Pas de DC)
    coast_both();          // Pins à la masse

    // IT
    TMR2IF = 0; TMR2IE = 0;
    PIR1bits.TMR1IF = 0; PIE1bits.TMR1IE = 0;

    PEIE = 1; GIE = 1;
    __delay_us(100);
}

// ==================== ISR ====================
void __interrupt() ISR(void){
    if (RCIF){
        if (RC1STAbits.OERR){ RC1STAbits.CREN=0; RC1STAbits.CREN=1; }
        if (RC1STAbits.FERR){ volatile uint8_t junk=RC1REG; (void)junk; RCIF=0; return; }
        RCIF=0; buffer=RC1REG; UART_processing();
    }
    else if (PIR1bits.TMR1IF){ // TRUE-SINE tick
        PIR1bits.TMR1IF = 0;
        if (!wave_mode) return;

        // reload
        TMR1H = (uint8_t)(t1_reload >> 8);
        TMR1L = (uint8_t)(t1_reload & 0xFF);

        // phase suivante
        uint8_t i = phase_idx + 1u; if (i >= SINE_LEN) i = 0; phase_idx = i;
        int8_t  s8 = SINE64_8[i];
        int8_t  sgn = (s8 > 0) ? +1 : ((s8 < 0) ? -1 : last_sign);

        if (!scale){
            coast_both(); set_pwm10(0); last_sign = sgn; return;
        }
        if (sgn != last_sign){
            coast_both(); route_halfcycle(sgn); last_sign = sgn;
        }

        // amplitude
        uint16_t mag = (uint16_t)(s8 >= 0 ? s8 : -s8);
        uint32_t tmp = (uint32_t)scale * (uint32_t)mag;
        uint16_t duty_fwd = (uint16_t)((tmp + 64u) >> 7);

        uint16_t top = (uint16_t)(4u * ((uint16_t)PR2 + 1u) - 1u);
        if (duty_fwd >= top) duty_fwd = top;
        set_pwm10(top - duty_fwd);
    }
    else if (TMR2IF){
        TMR2IF = 0;
        if (!wave_mode){
            index200++; if (index200 == 200) index200 = 0;
            square_tick = 1;
        }
    }
}

// ==================== Main ====================
int main(void){
    // --- BLOC SECURITE DEMARRAGE (ANTI-CHAUFFE) ---
    LATA = 0;             // Force toutes les sorties à 0V
    TRISA = 0b00111100;   // RA0, RA1 en SORTIE (0V)
    ANSELA = 0;           // Tout numérique
    CWG1CON0 = 0;         // Assure que CWG est OFF
    // -----------------------------------------------

    usart_init();
    pwm_cwg_init();
    SPI_Init();

    set_pwm10(0);

    for(;;){
        // LED hors ISR
        if (uart_led_flag){
            uart_led_flag = 0;
            if (color_index != duty5_raw){
                color_index = duty5_raw;
                getColor32(color_index, color);
                uint8_t gie = INTCONbits.GIE; INTCONbits.GIE = 0;
                sendColor_SPI(color[0], color[1], color[2]);
                INTCONbits.GIE = gie;
            }
        }
        // Square main loop
        if (square_tick){
            square_processing();
            square_tick = 0;
        }
    }
    return 0;
}