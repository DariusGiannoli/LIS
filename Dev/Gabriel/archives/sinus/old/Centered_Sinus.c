/*  main.c — PIC16F18313
 *  - PC/Arduino inchangés
 *  - START: addr, duty5 (0..31), freq_idx (0..7)
 *  - STOP:  addr seul (start=0)
 */

#include <xc.h>
#include <stdint.h>
#include <stdlib.h>
#include "neopixel_control.h"   // SPI_Init(), sendColor_SPI()

// ================== Configuration bits ==================
#pragma config FEXTOSC = OFF
#pragma config RSTOSC  = HFINT32
#pragma config CLKOUTEN= OFF
#pragma config CSWEN   = OFF
#pragma config FCMEN   = OFF
#pragma config MCLRE   = ON
#pragma config PWRTE   = OFF
#pragma config WDTE    = OFF
#pragma config LPBOREN = OFF
#pragma config BOREN   = OFF
#pragma config BORV    = LOW
#pragma config PPS1WAY = OFF
#pragma config STVREN  = ON
#pragma config DEBUG   = OFF
#pragma config WRT     = OFF
#pragma config LVP     = OFF
#pragma config CP      = OFF
#pragma config CPD     = OFF

#define _XTAL_FREQ 32000000u

// ================== Protocole / état ==================
static volatile uint8_t buffer = 0;
static volatile uint8_t uart_recv_flag = 0;

static volatile uint8_t duty_cycle = 0;   // 0..99 (depuis duty5)
static volatile uint8_t duty_index  = 0;  // 0..15 (LED)
static volatile uint8_t freq_index  = 3;  // 0..7

// Freq mécaniques (Hz) pour indices 0..7 (identiques à tes docs)
static const uint16_t FREQ_HZ[8] = {123, 145, 170, 200, 235, 275, 322, 384};

// FSM protocole
static volatile uint8_t state = 0;        // 0 idle, 1 wait duty, 2 wait freq
static volatile uint8_t temp_duty5 = 0;   // 0..31

// LED
static uint8_t color_index = 0;
static uint8_t color[3]    = {0,0,0};

// ================== Sinus engine (Timer1 + PWM 40k) ==================
#define SINE_LEN   24u          // échantillons par période
#define SINE_SCALE 1023u
#define CCP1_PPS   0x0C         // code PPS de CCP1 sur PIC16F18313
#define MIN_DRIVE_TICKS 2u      // plancher pour éviter grésillement près de 0

// LUT sinus (±1023), 24 points
static const int16_t SIN[SINE_LEN] = {
       0,   267,   517,   728,   885,   975,  1023,   975,
     885,   728,   517,   267,     0,  -267,  -517,  -728,
    -885,  -975, -1023,  -975,  -885,  -728,  -517,  -267
};

// État interne sinus
static volatile uint8_t  phase_idx = 0;   // 0..SINE_LEN-1
static volatile int8_t   last_sign = 0;   // -1 / +1
static volatile uint16_t t1_reload = 0;   // reload TMR1 (1 µs ticks)
static volatile uint16_t duty_max  = 0;   // 799 (PR2=199)
static volatile uint16_t scale     = 0;   // (duty_max * amp%)/100

// --- helpers PWM/route ---
static inline void set_pwm10(uint16_t d){ CCPR1H = d >> 8; CCPR1L = d & 0xFF; }

// déconnecte CCP1 des pins et met RA0/RA1 à 0 (coast)
static inline void coast_both(void){
    RA1PPS = 0; LATAbits.LATA1 = 0;
    RA0PPS = 0; LATAbits.LATA0 = 0;
}

// route une demi-onde: signe>0 -> RA1=1 et PWM sur RA0 ; signe<0 -> RA0=1 et PWM sur RA1
static inline void route_halfcycle(int8_t sign){
    if (sign > 0){ LATAbits.LATA1 = 1; RA0PPS = CCP1_PPS; } // +
    else          { LATAbits.LATA0 = 1; RA1PPS = CCP1_PPS; } // -
}

// Timer1: calcule reload pour Fs = freq_hz * SINE_LEN (prescaler 1:8 -> 1 µs tick)
static void t1_set_freq(uint16_t freq_hz){
    if (freq_hz == 0) freq_hz = 1;
    uint32_t Fs = (uint32_t)freq_hz * (uint32_t)SINE_LEN;
    uint32_t tick_ns = 1000ul; // 1 µs = 1000 ns (prescaler 1:8)
    // ticks = round(1e9 / (Fs * 1e3)) = round(1e6 / Fs)
    uint32_t ticks_per_sample = (1000000ul + Fs/2) / Fs; // arrondi
    if (ticks_per_sample < 5) ticks_per_sample = 5;
    if (ticks_per_sample > 60000ul) ticks_per_sample = 60000ul;
    t1_reload = (uint16_t)(65536ul - ticks_per_sample);

    T1CONbits.TMR1ON = 0;
    TMR1H = (uint8_t)(t1_reload >> 8);
    TMR1L = (uint8_t)(t1_reload & 0xFF);
    PIR1bits.TMR1IF = 0;
    T1CONbits.TMR1ON = 1;
}

// Amplitude en % (0..100)
static inline void lra_set_amp(uint8_t amp_pct){
    if (amp_pct > 100) amp_pct = 100;
    scale = (uint16_t)((uint32_t)duty_max * amp_pct / 100u);
    if (scale == 0u){
        coast_both();
        set_pwm10(0);
    }
}

// Init PWM (40 kHz) + Timer1 (ISR off jusqu’au START)
static void lra_init(void){
    // GPIO
    ANSELA = 0x00;
    TRISAbits.TRISA1 = 0;
    TRISAbits.TRISA0 = 0;
    coast_both();

    // PWM 40 kHz (TMR2 @ Fosc/4 = 8 MHz)
    PR2 = 199;                                // 8 MHz / (199+1) = 40 kHz ticks
    duty_max = (uint16_t)((PR2 + 1u) * 4u - 1u); // 799
    T2CON = 0; T2CONbits.T2CKPS = 0b00; T2CONbits.TMR2ON = 1;
    PIR1bits.TMR2IF = 0; while(!PIR1bits.TMR2IF); PIR1bits.TMR2IF = 0;

    // CCP1 PWM right-aligned
    CCP1CON = 0b10001111;
    set_pwm10(0);

    // Timer1 à 1 µs/tick (Fosc/4, prescaler 1:8)
    T1CON = 0;
    T1CONbits.T1CKPS = 0b11; // 1:8
    // pas de démarrage ici; t1_set_freq() l'activera

    // IT
    PIE1bits.TMR1IE = 1;
    INTCONbits.PEIE = 1;
    INTCONbits.GIE  = 1;

    // état sinus
    phase_idx = 0; last_sign = 0; scale = 0;
    coast_both();
}

// Unmap 5-bit -> 0..99
static inline uint8_t map5bit_to_0_99(uint8_t v){
    if (v > 31u) v = 31u;
    return (uint8_t)(((uint16_t)v * 99u + 15u) / 31u); // round(v*99/31)
}

// ================== UART protocole (inchangé côté PC/Arduino) ==================
static inline uint8_t make_addr_byte(uint8_t start, uint8_t addr){
    return (uint8_t)((start & 0x1u) | (addr << 1));
}

static void UART_Write(uint8_t data){ while(!TRMT){} TX1REG = data; }

static void usart_init(void){
    TRISA5 = 1;   // RX
    TRISA2 = 1;   // TX
    ANSELA = 0;

    RXPPS  = 0b00101;  // RA5->RX
    RA2PPS = 0b10100;  // TX->RA2

    RC1STA   = 0b10010000; // SPEN=1 CREN=1
    TX1STA   = 0b00100100; // BRGH=1 TXEN=1
    BAUD1CON = 0b00001000; // BRG16=1
    SP1BRGH  = 0;
    SP1BRGL  = 68;         // 115200 @ 32MHz

    RCIE = 1;
    __delay_us(100);
}

static void UART_processing(void){
    // MSB=0 -> Adresse
    if ((buffer >> 7) == 0){
        uint8_t addr  = (buffer >> 1);
        uint8_t start = (buffer & 0x1u);

        if (addr != 0){
            state = 0;
            --addr;
            UART_Write(make_addr_byte(start, addr)); // forward
            return;
        }else{
            if (start == 0){
                // STOP: coupe Timer1, met en coast
                state = 0;
                T1CONbits.TMR1ON = 0;
                coast_both();
                set_pwm10(0);
                duty_cycle = 0;
                duty_index = 0;
            }else{
                // START -> attendre DUTY (5 bits)
                state = 1;
            }
            return;
        }
    }
    // MSB=1 -> Donnée
    else {
        switch(state){
            case 0: // non adressé -> forward
                UART_Write(buffer);
                break;

            case 1: // DUTY5 (0..31)
                temp_duty5 = (uint8_t)(buffer & 0x1Fu);
                state = 2;
                break;

            case 2: // FREQ3 (0..7)
            {
                freq_index = (uint8_t)(buffer & 0x07u);

                // Appliquer settings
                duty_cycle = map5bit_to_0_99(temp_duty5);     // 0..99
                if (duty_cycle > 99u) duty_cycle = 99u;

                // Amplitude sinus en % = duty_cycle (0..99)
                lra_set_amp(duty_cycle);

                // Démarre / ajuste la fréquence mécanique
                uint16_t f = FREQ_HZ[freq_index];
                t1_set_freq(f);

                // réinit phase pour démarrer propre
                phase_idx = 0;
                last_sign = 0;

                // LED (index 0..15)
                duty_index = (uint8_t)(((uint16_t)duty_cycle * 16u) / 100u);
                if (duty_index > 15u) duty_index = 15u;

                state = 0;
            } break;

            default:
                state = 0;
                break;
        }
    }
}

// ================== LED helper ==================
static void getColor(uint8_t di, uint8_t out[3]){
    if(di > 15) di = 15;
    switch(di){
        case 0:  out[0]=0;   out[1]=0;   out[2]=0;   break;
        case 1:  out[0]=0;   out[1]=32;  out[2]=32;  break;
        case 2:  out[0]=0;   out[1]=64;  out[2]=64;  break;
        case 3:  out[0]=0;   out[1]=128; out[2]=128; break;
        case 4:  out[0]=0;   out[1]=255; out[2]=255; break;
        case 5:  out[0]=0;   out[1]=255; out[2]=128; break;
        case 6:  out[0]=0;   out[1]=255; out[2]=0;   break;
        case 7:  out[0]=128; out[1]=255; out[2]=0;   break;
        case 8:  out[0]=255; out[1]=255; out[2]=0;   break;
        case 9:  out[0]=255; out[1]=128; out[2]=0;   break;
        case 10: out[0]=255; out[1]=0;   out[2]=0;   break;
        case 11: out[0]=255; out[1]=0;   out[2]=128; break;
        case 12: out[0]=255; out[1]=0;   out[2]=255; break;
        case 13: out[0]=128; out[1]=0;   out[2]=255; break;
        case 14: out[0]=64;  out[1]=0;   out[2]=255; break;
        case 15: out[0]=255; out[1]=255; out[2]=255; break;
        default: out[0]=0;   out[1]=0;   out[2]=0;   break;
    }
}

// ================== ISR ==================
void __interrupt() ISR(void){
    if (RCIF){
        // Robustesse RX (optionnel) :
        if (RC1STAbits.OERR){ RC1STAbits.CREN = 0; RC1STAbits.CREN = 1; }
        if (RC1STAbits.FERR){ volatile uint8_t junk = RC1REG; (void)junk; RCIF=0; return; }

        RCIF = 0;
        buffer = RC1REG;
        UART_processing();
        uart_recv_flag = 1;
    }
    else if (PIR1bits.TMR1IF){
        PIR1bits.TMR1IF = 0;

        // reload T1
        TMR1H = (uint8_t)(t1_reload >> 8);
        TMR1L = (uint8_t)(t1_reload & 0xFF);

        // avance phase
        uint8_t i = phase_idx + 1u;
        if (i >= SINE_LEN) i = 0;
        phase_idx = i;

        int16_t s = SIN[i];
        int8_t sign = (s > 0) ? +1 : ((s < 0) ? -1 : last_sign);

        if (scale == 0u){
            coast_both();
            set_pwm10(0);
            last_sign = sign;
            return;
        }

        // inversion de signe: bascule propre
        if (sign != last_sign){
            coast_both();
            route_halfcycle(sign);
            last_sign = sign;
        }

        // amplitude instantanée (fixed-point)
        uint16_t mag = (uint16_t)(s >= 0 ? s : -s); // 0..1023
        uint32_t tmp = (uint32_t)scale * (uint32_t)mag + 512u;
        uint16_t duty_forward = (uint16_t)(tmp >> 10);

        if (duty_forward <= MIN_DRIVE_TICKS){
            set_pwm10(duty_max);                 // brake/coast très proche de 0
        }else{
            uint16_t duty_inv = (uint16_t)(duty_max - duty_forward);
            set_pwm10(duty_inv);                 // PWM active-low
        }
    }
    else if (CCP1IF){
        CCP1IF = 0;
    }
}

// ================== main ==================
int main(void){
    lra_init();
    usart_init();
    SPI_Init();

    for(;;){
        if (uart_recv_flag){
            uart_recv_flag = 0;
            if (color_index != duty_index){
                color_index = duty_index;
                getColor(duty_index, color);
                sendColor_SPI(color[0], color[1], color[2]);
            }
        }
        // boucle vide : tout est cadencé par IT
    }
    return 0;
}