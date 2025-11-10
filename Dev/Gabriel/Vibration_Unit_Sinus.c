/* * File:   main.c (sinus-LUT drop-in)
 * Note:    Duty uses 5 bits (0..31) mapped to 0..99, waveform = sine via LUT
 */

#include <stdio.h>
#include <stdlib.h>
#include "neopixel_control.h"

// PIC16F18313 Configuration Bit Settings
// CONFIG1
#pragma config FEXTOSC = OFF
#pragma config RSTOSC  = HFINT32
#pragma config CLKOUTEN= OFF
#pragma config CSWEN   = OFF
#pragma config FCMEN   = OFF
// CONFIG2
#pragma config MCLRE   = ON
#pragma config PWRTE   = OFF
#pragma config WDTE    = OFF
#pragma config LPBOREN = OFF
#pragma config BOREN   = OFF
#pragma config BORV    = LOW
#pragma config PPS1WAY = OFF
#pragma config STVREN  = ON
#pragma config DEBUG   = OFF
// CONFIG3
#pragma config WRT     = OFF
#pragma config LVP     = OFF
// CONFIG4
#pragma config CP      = OFF
#pragma config CPD     = OFF

#include <xc.h>
#include <stdint.h>
#include <stdlib.h>

#define _XTAL_FREQ 32000000u

// UART
static volatile uint8_t buffer = 0;
static volatile uint8_t uart_recv_flag = 0;

// Duty/Frequency state
static volatile uint8_t duty_cycle = 0;     // 0..99 (from 5-bit)
static volatile uint8_t duty_index  = 0;    // 0..15 for LED color only
static volatile uint8_t freq_index  = 3;    // 0..7
static const uint8_t PR_val[8] = {85, 72, 60, 52, 44, 37, 32, 27};

// Flags & ISR helpers
static volatile uint8_t ccp_flag = 0;
static volatile uint8_t cwg_flag = 0;
static volatile uint8_t duty_flag = 0;
static volatile uint8_t index     = 0;

// Byte framing FSM
static volatile uint8_t state = 0;
static volatile uint8_t temp_duty5 = 0;

// neopixel color
static uint8_t color_index = 0;
static uint8_t color[3]    = {0,0,0};

// ================== NEW: SINE LUT (100 points, 0..100%) ==================
static const uint8_t SINE_0_100[100] = {
  0,  3,  6, 10, 13, 16, 19, 22, 25, 28, 31, 34, 37, 40, 43, 46, 49, 51, 54, 57,
 59, 62, 64, 67, 69, 71, 73, 76, 78, 80, 81, 83, 85, 87, 88, 90, 91, 92, 93, 95,
 95, 96, 97, 98, 98, 99, 99,100,100,100,100,100,100, 99, 99, 98, 98, 97, 96, 95,
 95, 93, 92, 91, 90, 88, 87, 85, 83, 81, 80, 78, 76, 73, 71, 69, 67, 64, 62, 59,
 57, 54, 51, 49, 46, 43, 40, 37, 34, 31, 28, 25, 22, 19, 16, 13, 10,  6,  3,  0
};
// ========================================================================

// ---------- Helpers ----------
static inline uint8_t make_addr_byte(uint8_t start, uint8_t addr){
    uint8_t addr_byte = 0;
    addr_byte |= (start & 0x1u);
    addr_byte |= (uint8_t)(addr << 1);
    return addr_byte;
}

// Map 5-bit (0..31) to 0..99 with rounding
static inline uint8_t map5bit_to_0_99(uint8_t v){
    if(v > 31u) v = 31u;
    uint16_t x = (uint16_t)v * 99u + 15u;
    return (uint8_t)(x / 31u);
}

static void UART_Write(uint8_t data){
    while(!TRMT) {;}
    TX1REG = data;
}

// ---------- Peripherals ----------
static void init_ccp_cwg(void){
    TRISA0 = 1;
    TRISA1 = 1;

    ANSELA = 0;   // digital
    WPUA   = 0;

    RA1PPS = 0b01000; // CWG1A
    RA0PPS = 0b01001; // CWG1B

    CCP1CON = 0b10011111; // PWM, FMT=1
    CCP1IE  = 1;

    T2CON = 0b00000001;   // prescale set, TMR2 off for now
    PR2   = PR_val[freq_index];
    TMR2IE = 1;

    // CWG exactement comme ton code qui marche
    CWG1CON0   = 0b01000100; // half-bridge, disabled
    CWG1CON1   = 0;          // (on changera POLB dynamiquement comme avant)
    CWG1DAT    = 0b00000011; // input = CCP1
    CWG1AS0    = 0b01111000; // shutdown config
    CWG1DBR    = 0;          // deadband off (comme avant)
    CWG1DBF    = 0;
    CWG1CLKCON = 1;          // HFINTOSC
    CWG1CON0bits.EN = 1;

    PEIE = 1;
    GIE  = 1;

    __delay_us(100);
}

static void usart_init(void){
    TRISA5 = 1;  // RX
    TRISA2 = 1;  // TX

    ANSELA = 0;

    RXPPS  = 0b00101; // RA5 -> RX
    RA2PPS = 0b10100; // TX -> RA2

    RC1STA   = 0b10010000; // SPEN=1, CREN=1
    TX1STA   = 0b00100100; // BRGH=1, TXEN=1
    BAUD1CON = 0b00001000; // BRG16=1

    SP1BRGH  = 0;
    SP1BRGL  = 68;         // 115200 @ 32MHz

    RCIE = 1;

    __delay_us(100);
}

// ---------- Protocol handling ----------
static void UART_processing(void){
    if((buffer >> 7) == 0){ // Address byte
        uint8_t addr  = (buffer >> 1);
        uint8_t start = (buffer & 0x1u);

        if(addr != 0){
            state = 0;
            --addr;
            UART_Write(make_addr_byte(start, addr)); // forward
            return;
        }else{
            if(start == 0){
                // STOP
                state     = 0;
                TMR2ON    = 0;
                TRISA0    = 1;
                TRISA1    = 1;
                duty_cycle= 0;
                duty_index= 0;
            }else{
                // START → expect DUTY
                state = 1;
            }
            return;
        }
    } else { // Data byte
        switch(state){
            case 0:
                UART_Write(buffer); // forward raw
                break;

            case 1: // DUTY (5 bits)
                temp_duty5 = (uint8_t)(buffer & 0x1Fu); // 0..31
                state = 2;
                break;

            case 2: // FREQ (3 bits)
            {
                freq_index = (uint8_t)(buffer & 0x07u);

                TRISA1 = 0;
                TRISA0 = 0;

                T2CON  = 0b00000101; // TMR2ON=1, prescale 1:4
                PR2    = PR_val[freq_index];

                duty_cycle = map5bit_to_0_99(temp_duty5);
                if(duty_cycle > 99u) duty_cycle = 99u;

                duty_index = (uint8_t)(((uint16_t)duty_cycle * 16u) / 100u);
                if(duty_index > 15u) duty_index = 15u;

                state = 0;
            }   break;

            default:
                state = 0;
                break;
        }
        return;
    }
}

// ================== NEW: helper pour régler la PWM en % ==================
static inline void set_pwm_pct(uint8_t pct){
    if (pct > 100) pct = 100;
    uint16_t h = ((uint16_t)PR_val[freq_index] * pct + 50) / 100;
    CCPR1H = (uint8_t)h;
    CCPR1L = 0x00;
}
// ========================================================================

// ---------- PWM/Bridge drive (SINUS LUT, mais logique CWG intacte) ----------
static void CCP_processing(void){
    // Calcul de l’enveloppe sinus (0..99 → 0..100 %) pour 0..199
    uint8_t k = (index < 100) ? index : (uint8_t)(199 - index); // 0..99
    uint8_t env = SINE_0_100[k];                                // 0..100
    // Échelle par le duty utilisateur 0..99
    uint16_t amp_pct_u16 = ((uint16_t)env * (uint16_t)duty_cycle + 50) / 100; // 0..99
    uint8_t  amp_pct = (uint8_t)amp_pct_u16;

    // Fenêtres ON identiques à ton code : 1ère moitié et 2ème moitié
    if( (index < duty_cycle) || (index >= 100 && index < (uint8_t)(100 + duty_cycle)) ){
        // ON → sorties opposées (comme avant) et PWM = amplitude sinus
        if (cwg_flag == 0){
            CWG1CON0bits.EN = 0;
            CWG1CON1bits.POLB = 0;  // "opposite" selon ta logique existante
            CWG1CON0bits.EN = 1;
            cwg_flag = 1;
        }
        // PWM variable suivant l’enveloppe sinus
        set_pwm_pct(amp_pct);
        duty_flag = 1;
    } else {
        // OFF → sorties identiques (diff=0) + quasi zéro PWM (comme avant)
        if (cwg_flag == 1){
            CWG1CON0bits.EN = 0;
            CWG1CON1bits.POLB = 1;  // "same" selon ta logique existante
            CWG1CON0bits.EN = 1;
            cwg_flag = 0;
        }
        // proche de zéro
        CCPR1H = 0x00;
        CCPR1L = 64;
        duty_flag = 0;
    }
}

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

// ---------- Interrupts ----------
void __interrupt() ISR(void){
    if(RCIF){
        RCIF = 0;
        buffer = RC1REG;
        UART_processing();
        uart_recv_flag = 1;
    }else if(TMR2IF){
        TMR2IF = 0;
        index++;
        if(index == 200) index = 0;
        ccp_flag = 1;
    }else if(CCP1IF){
        CCP1IF = 0;
    }
}

// ---------- Main ----------
int main(void){
    init_ccp_cwg();
    usart_init();
    SPI_Init();

    for(;;){
        if(uart_recv_flag){
            uart_recv_flag = 0;
            if(color_index != duty_index){
                color_index = duty_index;
                getColor(duty_index, color);
                sendColor_SPI(color[0], color[1], color[2]);
            }
        }
        if(ccp_flag){
            CCP_processing();   // même point d’entrée qu’avant
            ccp_flag = 0;
        }
    }
    return 0;
}