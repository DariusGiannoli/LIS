/* * File:   main.c
 * Author:  MasonC (updated)
 * Note:    Square-wave drive — Duty uses 5 bits (0..31) mapped to 0..99 for actuation,
 *          and LED color index uses the raw 5-bit duty (0..31) with 16-key palette + interpolation.
 */

#include <stdio.h>
#include <stdlib.h>
#include "neopixel_control.h"

// PIC16F18313 Configuration Bit Settings
// CONFIG1
#pragma config FEXTOSC = OFF     // Oscillator not enabled
#pragma config RSTOSC  = HFINT32 // HFINTOSC (32 MHz)
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
// duty_cycle is 0..99 after mapping 5-bit duty
static volatile uint8_t duty_cycle = 0;     // 0..99
static volatile uint8_t duty_index  = 0;    // 0..31 (LED color index aligned to raw duty5)
static volatile uint8_t freq_index  = 3;    // 0..7 -> PR2 from table below
static const uint8_t PR_val[8] = {85, 72, 60, 52, 44, 37, 32, 27};

// Flags & ISR helpers
static volatile uint8_t ccp_flag = 0;
static volatile uint8_t cwg_flag = 0;
static volatile uint8_t duty_flag = 0;
static volatile uint8_t index     = 0;

// Byte framing state machine
// state 0 = idle/not addressed
// state 1 = got START for addr==0, expect Data Byte 1 (5-bit duty)
// state 2 = got duty, expect Data Byte 2 (freq index)
static volatile uint8_t state = 0;

// Temp store for 5-bit duty before mapping
static volatile uint8_t temp_duty5 = 0;

// neopixel color
static uint8_t color_index = 0;
static uint8_t color[3]    = {0,0,0};

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
    // round( v * 99 / 31 ) using integer math
    uint16_t x = (uint16_t)v * 99u + 15u; // +15 ~= /2 for rounding
    return (uint8_t)(x / 31u);
}

static void UART_Write(uint8_t data){
    while(!TRMT) {;}
    TX1REG = data;
}

// ---------- Peripherals ----------
static void init_ccp_cwg(void){
    // Disable outputs during setup
    TRISA0 = 1;
    TRISA1 = 1;

    ANSELA = 0;   // digital
    WPUA   = 0;   // no weak pullups

    // PPS: CWG outputs on RA1 (CWG1A) and RA0 (CWG1B)
    RA1PPS = 0b01000; // CWG1A
    RA0PPS = 0b01001; // CWG1B

    // CCP1 PWM, FMT=1
    CCP1CON = 0b10011111;
    CCP1IE  = 1;

    // Timer2
    T2CON = 0b00000001; // prescale set, TMR2 off for now
    PR2   = PR_val[freq_index];
    TMR2IE = 1;

    // CWG configuration
    CWG1CON0   = 0b01000100; // Half-bridge, disabled for now
    CWG1CON1   = 0;          // A non-invert, B invert
    CWG1DAT    = 0b00000011; // input from CCP1
    CWG1AS0    = 0b01111000; // shutdown config
    CWG1DBR    = 0;
    CWG1DBF    = 0;
    CWG1CLKCON = 1;          // HFINTOSC
    CWG1CON0bits.EN = 1;

    // Interrupts
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
    SP1BRGL  = 68;         // 115200 baud @ 32MHz

    RCIE = 1;              // RX interrupt

    __delay_us(100);
}

// ---------- Protocol handling ----------
static void UART_processing(void){
    // Address byte: MSB==0
    if((buffer >> 7) == 0){
        uint8_t addr  = (buffer >> 1);
        uint8_t start = (buffer & 0x1u);

        if(addr != 0){
            state = 0;     // not for us -> forward with addr-1
            --addr;
            UART_Write(make_addr_byte(start, addr));
            return;
        }else{
            if(start == 0){
                // STOP
                state     = 0;
                TMR2ON    = 0;     // stop PWM
                TRISA0    = 1;     // tri-state outputs
                TRISA1    = 1;
                duty_cycle= 0;
                duty_index= 0;
            }else{
                // START -> expect Data Byte 1 (5-bit duty)
                state = 1;
            }
            return;
        }
    }
    // Data byte: MSB==1
    else{
        switch(state){
            case 0: // not addressed -> forward raw
                UART_Write(buffer);
                break;

            case 1: // expect duty (5 bits in b[4:0])
                temp_duty5 = (uint8_t)(buffer & 0x1Fu); // 0..31
                state = 2;
                break;

            case 2: // expect frequency index (3 bits in b[2:0])
            {
                freq_index = (uint8_t)(buffer & 0x07u);

                // Apply settings
                TRISA1 = 0;
                TRISA0 = 0;

                // Turn on TMR2 (prescale/postscale previously set)
                T2CON  = 0b00000101; // ensure TMR2ON=1 with desired prescale
                PR2    = PR_val[freq_index];

                // Map 5-bit duty to 0..99 for actuation windowing
                duty_cycle = map5bit_to_0_99(temp_duty5);
                if(duty_cycle > 99u) duty_cycle = 99u;

                // === LED COLOR: 32 steps aligned with raw duty5 ===
                duty_index = temp_duty5; // 0..31

                state = 0; // transaction complete
            }   break;

            default:
                state = 0;
                break;
        }
        return;
    }
}

// ---------- PWM/Bridge drive (square-window logic unchanged) ----------
static void CCP_processing(void){
    // CWG polarity switching based on duty window within a 200-tick frame
    if( (index < duty_cycle) || (index >= 100 && index < (uint8_t)(100 + duty_cycle)) ){
        if(cwg_flag == 0){
            CWG1CON0bits.EN = 0;
            CWG1CON1bits.POLB = 0;  // A/B opposite
            CWG1CON0bits.EN = 1;
            cwg_flag = 1;
        }
    }else{
        if(cwg_flag == 1){
            CWG1CON0bits.EN = 0;
            CWG1CON1bits.POLB = 1;  // A/B same
            CWG1CON0bits.EN = 1;
            cwg_flag = 0;
        }
    }

    // CCP duty block
    if(index < duty_cycle){
        if(duty_flag == 0){
            // "high" duty slice
            CCPR1H = PR_val[freq_index];
            CCPR1L = 0x00;
            duty_flag = 1;
        }
    }else{
        if(duty_flag == 1){
            // "low" duty slice (very small)
            CCPR1H = 0x00;
            CCPR1L = 64;
            duty_flag = 0;
        }
    }
}

// ================== Colors: 16 keys + interpolation to 32 ==================
// 16 couleurs d’origine (en flash)
static const uint8_t KEY16[16][3] = {
  {  0,  0,  0},  {  0, 32, 32},  {  0, 64, 64},  {  0,128,128},
  {  0,255,255},  {  0,255,128},  {  0,255,  0},  {128,255,  0},
  {255,255,  0},  {255,128,  0},  {255,  0,  0},  {255,  0,128},
  {255,  0,255},  {128,  0,255},  { 64,  0,255},  {255,255,255}
};

// 0..31 → couleur : pairs = clés, impairs = moyenne entre deux clés (sauf 31 → dernière clé)
static inline void getColor32(uint8_t idx32, uint8_t out[3]) {
    if (idx32 > 31) idx32 = 31;
    uint8_t seg  = idx32 >> 1;    // 0..15
    uint8_t odd  = idx32 & 1;     // 0 pair / 1 impair

    if (!odd || seg >= 15) {
        out[0] = KEY16[seg][0];
        out[1] = KEY16[seg][1];
        out[2] = KEY16[seg][2];
    } else {
        out[0] = (uint8_t)((KEY16[seg][0] + KEY16[seg+1][0]) >> 1);
        out[1] = (uint8_t)((KEY16[seg][1] + KEY16[seg+1][1]) >> 1);
        out[2] = (uint8_t)((KEY16[seg][2] + KEY16[seg+1][2]) >> 1);
    }
}

static void getColor(uint8_t di, uint8_t out[3]) {
    // backward-compat wrapper: now expects 0..31 and calls getColor32
    getColor32(di, out);
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

    // Main loop
    for(;;){
        if(uart_recv_flag){
            uart_recv_flag = 0;
            // update neopixel color only when the level bucket changes
            if(color_index != duty_index){
                color_index = duty_index;          // 0..31 now
                getColor32(color_index, color);
                sendColor_SPI(color[0], color[1], color[2]);
            }
        }
        if(ccp_flag){
            CCP_processing();
            ccp_flag = 0;
        }
    }
    // not reached
    return 0;
}