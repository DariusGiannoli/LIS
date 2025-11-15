/*  main.c — PIC16F18313
 *  3-byte proto via ESP → PIC: Addr byte, Data1 (duty5), Data2 (wave<<3 | freq3)
 *  wave=1 → True-sine (Timer1 + LUT 64 pts en 8 bits, PWM 40 kHz)
 *  wave=0 → Square-window engine (TMR2IF fenêtrage, PR2 table)
 *  Mapping duty5 (0..31) → % (0..99) LUT 32 valeurs (commune aux 2 modes)
 */

#include <xc.h>
#include <stdint.h>
#include <stdlib.h>
#include "neopixel_control.h"

#pragma config FEXTOSC=OFF, RSTOSC=HFINT32, CLKOUTEN=OFF, CSWEN=OFF, FCMEN=OFF
#pragma config MCLRE=ON, PWRTE=OFF, WDTE=OFF, LPBOREN=OFF, BOREN=OFF, BORV=LOW, PPS1WAY=OFF, STVREN=ON, DEBUG=OFF
#pragma config WRT=OFF, LVP=OFF, CP=OFF, CPD=OFF

#define _XTAL_FREQ 32000000u

// ====== Protocole/state ======
static volatile uint8_t buffer=0, uart_recv_flag=0;

static volatile uint8_t duty_cycle=0; // 0..99 (depuis LUT)
static volatile uint8_t duty_index =0; // 0..31 (LED)
static volatile uint8_t freq_index =3; // 0..7
static volatile uint8_t wave_mode =1;  // 1=sine (default), 0=square

// FREQ pour sinus (Hz)
static const uint16_t FREQ_HZ[8] = {123,145,170,200,235,275,322,384};

// PR2 table pour square (héritée)
static const uint8_t PR_val[8] = {85,72,60,52,44,37,32,27};

// UART FSM
static volatile uint8_t state=0, temp_duty5=0;

// LED
static uint8_t color_index=0, color[3]={0,0,0};

// ====== True-sine engine ======
#define SINE_LEN 64u
#define CCP1_PPS 0x0C
#define MIN_DRIVE_TICKS 2u

// LUT sinus 8 bits (±127) — compacte
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

static volatile uint8_t  phase_idx=0;
static volatile int8_t   last_sign=0;
static volatile uint16_t t1_reload=0, duty_max=0, scale=0;

static inline void set_pwm10(uint16_t d){ CCPR1H=d>>8; CCPR1L=d&0xFF; }

static inline void coast_both(void){ RA1PPS=0; LATAbits.LATA1=0; RA0PPS=0; LATAbits.LATA0=0; }

static inline void route_halfcycle(int8_t sign){
    if (sign>0){ LATAbits.LATA1=1; RA0PPS=CCP1_PPS; }  // + : RA1=1, PWM sur RA0
    else        { LATAbits.LATA0=1; RA1PPS=CCP1_PPS; } // - : RA0=1, PWM sur RA1
}

static void t1_set_freq(uint16_t freq_hz){
    if (!freq_hz) freq_hz=1;
    uint32_t Fs = (uint32_t)freq_hz * (uint32_t)SINE_LEN;
    uint32_t ticks = (1000000ul + Fs/2) / Fs; // 1us tick
    if (ticks<5) ticks=5; if (ticks>60000ul) ticks=60000ul;
    t1_reload = (uint16_t)(65536ul - ticks);
    T1CONbits.TMR1ON=0;
    TMR1H=(uint8_t)(t1_reload>>8); TMR1L=(uint8_t)(t1_reload&0xFF);
    PIR1bits.TMR1IF=0; T1CONbits.TMR1ON=1;
}

static inline void lra_set_amp(uint8_t pct){
    if (pct>100) pct=100;
    scale = (uint16_t)((uint32_t)duty_max * pct / 100u); // 0..799
    if (!scale){ coast_both(); set_pwm10(0); }
}

// ====== Square engine (corrigé polarités) ======
static volatile uint8_t index200=0, cwg_flag=0, duty_flag=0;

static void square_processing(void){
    // Fenêtre ON: [0..duty_cycle) et [100..100+duty_cycle)
    uint8_t on =
        (index200 < duty_cycle) ||
        (index200 >= 100 && index200 < (uint8_t)(100 + duty_cycle));

    if (on){
        // A/B OPPOSÉES → B inversé (POLB=0 selon ton montage d’origine)
        if (cwg_flag == 0){
            CWG1CON0bits.EN = 0;
            CWG1CON1bits.POLA = 0;   // A non-inverti
            CWG1CON1bits.POLB = 0;   // ⬅️ opposées en ON (comme ta version qui vibrait)
            CWG1CON0bits.EN = 1;
            cwg_flag = 1;
        }
        if (duty_flag == 0){
            CCPR1H = PR_val[freq_index]; // quasi plein
            CCPR1L = 0x00;
            duty_flag = 1;
        }
    } else {
        // A/B IDENTIQUES → B inversé (POLB=1) pour neutraliser la diff
        if (cwg_flag == 1){
            CWG1CON0bits.EN = 0;
            CWG1CON1bits.POLB = 1;   // ⬅️ identiques en OFF
            CWG1CON0bits.EN = 1;
            cwg_flag = 0;
        }
        if (duty_flag == 1){
            CCPR1H = 0x00;  // quasi zéro
            CCPR1L = 64;
            duty_flag = 0;
        }
    }
}

// ====== LUT duty5 (0..31) → % (0..99), commune square/sine ======
static const uint8_t DUTY5_TO_PCT[32] = {
  0,  0,  1,  1,  1,  2,  3,  4,
  5,  6,  7,  9, 11, 13, 15, 18,
 20, 24, 27, 30, 34, 38, 43, 48,
 53, 58, 64, 70, 77, 84, 91, 99
};

// ====== UART & init ======
static void usart_init(void){
    TRISA5=1; TRISA2=1; ANSELA=0;
    RXPPS=0b00101; RA2PPS=0b10100;
    RC1STA=0b10010000; TX1STA=0b00100100; BAUD1CON=0b00001000;
    SP1BRGH=0; SP1BRGL=68;
    RCIE=1; __delay_us(100);
}

static void pwm_timers_init(void){
    // PWM 40k (Timer2)
    PR2=199; duty_max=(uint16_t)((PR2+1u)*4u - 1u);
    T2CON=0; T2CONbits.T2CKPS=0b00; T2CONbits.TMR2ON=1;
    PIR1bits.TMR2IF=0; while(!PIR1bits.TMR2IF); PIR1bits.TMR2IF=0;
    CCP1CON=0b10001111; set_pwm10(0);

    // Timer1 @ 1us tick
    T1CON=0; T1CONbits.T1CKPS=0b11;

    // CWG pour square (sorties A/B sur RA1/RA0)
    RA1PPS=0b01000; RA0PPS=0b01001;      // CWG1A/CWG1B
    CWG1CLKCON=1; CWG1DAT=0b00000011;    // source = CCP1
    CWG1CON1=0; CWG1AS0=0b01111000;
    CWG1DBR=0; CWG1DBF=0;
    CWG1CON0=0b01000100; CWG1CON0bits.EN=1;

    // IT
    PIE1bits.TMR1IE=1; // sine
    TMR2IE=1;          // square
    INTCONbits.PEIE=1; INTCONbits.GIE=1;
}

static inline uint8_t make_addr_byte(uint8_t start, uint8_t addr){ return (uint8_t)((start&1u)|(addr<<1)); }
static void UART_Write(uint8_t d){ while(!TRMT){} TX1REG=d; }

// reçoit protocole PIC (repacké par l’ESP)
static void UART_processing(void){
    if ((buffer>>7)==0){ // Addr byte (MSB=0)
        uint8_t addr=(buffer>>1), start=(buffer&1u);
        if (addr!=0){ state=0; --addr; UART_Write(make_addr_byte(start,addr)); return; }
        else{
            if (!start){ // STOP
                state=0;
                // coupe les moteurs et IRQ
                T1CONbits.TMR1ON=0; PIE1bits.TMR1IE=0; TMR2IE=0;
                coast_both(); set_pwm10(0);
                // remettre CWG par défaut (propre pour repartir en square)
                RA1PPS=0b01000; RA0PPS=0b01001; CWG1CON0bits.EN=1;
                duty_cycle=0; duty_index=0;
            } else {
                state=1; // attendre duty
            }
            return;
        }
    } else { // Data (MSB=1)
        switch(state){
            case 0: UART_Write(buffer); break;
            case 1: temp_duty5 = (uint8_t)(buffer & 0x1Fu); state=2; break;
            case 2:{
                uint8_t data2 = buffer & 0x7F; // MSB=1, payload sur 7 bits
                freq_index = data2 & 0x07;
                wave_mode  = (data2 >> 3) & 0x01; // bit WAVE

                // Mapping LUT commun + couleur
                duty_cycle = DUTY5_TO_PCT[temp_duty5 & 0x1F];   // 0..99
                duty_index = temp_duty5;                        // 0..31 (LED)

                if (wave_mode){ // ===== SINE =====
                    // CWG OFF, TMR1 ON, TMR2 OFF, routage PPS direct dans ISR
                    CWG1CON0bits.EN = 0;
                    PIE1bits.TMR1IE = 1; TMR2IE = 0;

                    PR2=199; duty_max=(uint16_t)((PR2+1u)*4u - 1u);
                    lra_set_amp(duty_cycle);
                    t1_set_freq(FREQ_HZ[freq_index]);
                    phase_idx=0; last_sign=0;
                    T1CONbits.TMR1ON=1;
                } else {       // ===== SQUARE =====
                    // stop sinus
                    T1CONbits.TMR1ON = 0; PIE1bits.TMR1IE = 0;

                    // ⚠️ Reconfig Timer2: prescaler 1:4 (match PR_val[]), postscaler 1:1
                    T2CONbits.TMR2ON = 0;
                    T2CONbits.T2CKPS = 0b01;      // 1:4
                    // T2OUTPS bits 6..3 = 0000 -> 1:1 (laisse par défaut si déjà 0000)
                    T2CONbits.TMR2ON = 1;

                    // CWG sur RA1/RA0
                    RA1PPS = 0b01000; RA0PPS = 0b01001; CWG1CON0bits.EN = 1;
                    TMR2IE = 1;

                    PR2 = PR_val[freq_index];      // maintenant cohérent avec 1:4
                    index200 = 0; cwg_flag = 0; duty_flag = 0;
                }
                state=0;
            } break;
            default: state=0; break;
        }
    }
}

// ===== Couleurs (32 niveaux) =====
static const uint8_t KEY16[16][3] = {
  {0,0,0}, {0,32,32}, {0,64,64}, {0,128,128},
  {0,255,255}, {0,255,128}, {0,255,0}, {128,255,0},
  {255,255,0}, {255,128,0}, {255,0,0}, {255,0,128},
  {255,0,255}, {128,0,255}, {64,0,255}, {255,255,255}
};

static inline void getColor32(uint8_t i, uint8_t out[3]){
    if (i>31) i=31;
    uint8_t seg=i>>1, odd=i&1;
    if (!odd || seg>=15){ out[0]=KEY16[seg][0]; out[1]=KEY16[seg][1]; out[2]=KEY16[seg][2]; }
    else {
        out[0]=(uint8_t)((KEY16[seg][0]+KEY16[seg+1][0])>>1);
        out[1]=(uint8_t)((KEY16[seg][1]+KEY16[seg+1][1])>>1);
        out[2]=(uint8_t)((KEY16[seg][2]+KEY16[seg+1][2])>>1);
    }
}

void main_init(void){
    ANSELA = 0;                 // digital
    TRISAbits.TRISA0 = 0;       // H-bridge outputs
    TRISAbits.TRISA1 = 0;

    pwm_timers_init();
    usart_init();
    SPI_Init();
}

// ===== ISR =====
void __interrupt() ISR(void){
    if (RCIF){
        if (RC1STAbits.OERR){ RC1STAbits.CREN=0; RC1STAbits.CREN=1; }
        if (RC1STAbits.FERR){ volatile uint8_t junk=RC1REG; (void)junk; RCIF=0; return; }
        RCIF=0; buffer=RC1REG; UART_processing(); uart_recv_flag=1;
    }
    else if (PIR1bits.TMR1IF){ // SINE engine tick
        PIR1bits.TMR1IF=0;
        if (!wave_mode) return;

        // reload T1
        TMR1H=(uint8_t)(t1_reload>>8); TMR1L=(uint8_t)(t1_reload&0xFF);

        // next phase & sample
        uint8_t i = phase_idx + 1u; if (i >= SINE_LEN) i = 0; phase_idx = i;
        int8_t s8 = SINE64_8[i];

        int8_t  sign = (s8 > 0) ? +1 : ((s8 < 0) ? -1 : last_sign);
        if (!scale){ coast_both(); set_pwm10(0); last_sign=sign; return; }
        if (sign != last_sign){ coast_both(); route_halfcycle(sign); last_sign=sign; }

        // mag 0..127 ; duty_forward ≈ scale * mag / 128 (arrondi)
        uint16_t mag = (uint16_t)(s8 >= 0 ? s8 : -s8);     // 0..127
        uint32_t tmp = (uint32_t)scale * (uint32_t)mag;    // jusque ~101k
        uint16_t duty_forward = (uint16_t)((tmp + 64u) >> 7); // /128 avec arrondi

        if (duty_forward <= MIN_DRIVE_TICKS) set_pwm10(duty_max);
        else set_pwm10((uint16_t)(duty_max - duty_forward));
    }
    else if (TMR2IF){ // Square engine tick (fenêtrage)
        TMR2IF=0;
        if (!wave_mode){
            index200++; if (index200==200) index200=0;
            square_processing();
        }
    }
    else if (CCP1IF){ CCP1IF=0; }
}

// ===== main =====
int main(void){
    main_init();
    for(;;){
        if (uart_recv_flag){
            uart_recv_flag=0;
            if (color_index != duty_index){
                color_index = duty_index;
                getColor32(color_index, color);
                uint8_t gie=INTCONbits.GIE; INTCONbits.GIE=0; // WS2812 critical timing
                sendColor_SPI(color[0], color[1], color[2]);
                INTCONbits.GIE=gie;
            }
        }
    }
    return 0;
}