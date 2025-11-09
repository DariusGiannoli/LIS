#include <stdio.h>
#include <stdlib.h>
#include "neopixel_control.h"

// PIC16F18313 Configuration Bit Settings

// CONFIG1
#pragma config FEXTOSC = OFF     // Oscillator not enabled
#pragma config RSTOSC  = HFINT32 // HFINTOSC (1MHz) on reset
#pragma config CLKOUTEN = OFF    // CLKOUT disabled
#pragma config CSWEN   = OFF     // Clock switch disabled
#pragma config FCMEN   = OFF     // Fail-Safe Clock Monitor disabled

// CONFIG2
#pragma config MCLRE   = ON      // MCLR/VPP pin is MCLR
#pragma config PWRTE   = OFF     // PWRT disabled
#pragma config WDTE    = OFF     // WDT disabled
#pragma config LPBOREN = OFF     // ULPBOR disabled
#pragma config BOREN   = OFF     // BOR disabled
#pragma config BORV    = LOW     // BOR at 2.45V
#pragma config PPS1WAY = OFF     // PPSLOCK can be set/cleared repeatedly
#pragma config STVREN  = ON      // Stack overflow/underflow causes Reset
#pragma config DEBUG   = OFF     // Background debugger disabled

// CONFIG3
#pragma config WRT     = OFF     // Self-write protection off
#pragma config LVP     = OFF     // Low-voltage programming disabled

// CONFIG4
#pragma config CP      = OFF     // Code protection disabled
#pragma config CPD     = OFF     // Data NVM code protection disabled

#include <xc.h>
#include <stdint.h>
#include <stdlib.h>

#define _XTAL_FREQ  32000000     // Set clock frequency 

// ---- New data-byte layout masks (MSB=1 indicates "data" frame) ----
// [6:2] duty (5 bits), [1:0] freq (2 bits)
#define DUTY_MASK  0x7C  // 0b01111100
#define FREQ_MASK  0x03  // 0b00000011

uint8_t buffer = 0;     // UART recv buffer
uint8_t parity = 0;     // UART recv parity bit
uint8_t uart_recv_flag = 0;

// 5-bit duty index (0..31) mapped to 0..99 by LUT
uint8_t duty_index = 0; // 0..31
const uint8_t duty_cycle_lut_5bit[32] = {
    // perceptual-ish progression; keeps CCP_processing() comparisons valid (0..99)
    0, 0, 0, 1, 2, 3, 4, 5, 7, 8, 10, 13, 15, 18, 20, 23,
    27, 30, 34, 38, 42, 46, 50, 55, 60, 65, 70, 76, 82, 88, 94, 99
};
uint8_t duty_cycle = 0;

// Reduce to 4 frequency options (2-bit index 0..3)
uint8_t freq_index = 1; // default index
const uint8_t PR_val[4] = {
    72,  // ~145 Hz
    52,  // ~200 Hz
    37,  // ~275 Hz
    27   // ~384 Hz
};

uint8_t ccp_flag = 0;
uint8_t cwg_flag = 0;
uint8_t duty_flag = 0;
// Index into 0..199 timing window (two 0..99 windows back-to-back)
uint8_t index = 0;
uint8_t state = 0; // 1 if the board is currently addressed

// neopixel color
uint8_t color_index = 0;
uint8_t color[] = {0,0,0};

void init_ccp_cwg(void) {
    // Set PA0, PA1 initially as inputs to disable outputs during setup
    TRISA0 = 1;
    TRISA1 = 1;
    ANSELA = 0; // all digital
    WPUA   = 0; // no weak pullups

    // PPS: route CWG outputs
    RA1PPS = 0b01000; // CWG1A -> RA1
    RA0PPS = 0b01001; // CWG1B -> RA0

    // CCP1 PWM, FMT=1
    CCP1CON = 0b10011111;
    CCP1IE  = 1;

    // Enable Global & Peripheral Interrupts
    GIE  = 1;
    PEIE = 1;

    // Timer2 interrupt
    TMR2IE = 1;

    // Timer2 prescaler = 1:4 (per original), do not start yet
    T2CON = 0b00000001;

    // Default PWM period from freq LUT
    PR2 = PR_val[freq_index];

    // CWG setup
    CWG1CON0 = 0b01000100; // half bridge, initially disabled
    CWG1CON1 = 0;          // A non-inv, B inv (per original comment)
    CWG1DAT  = 0b00000011; // data input from CCP1
    CWG1AS0  = 0b01111000; // shutdown config (all 0 when occurs)
    CWG1DBR  = 0;
    CWG1DBF  = 0;
    CWG1CLKCON = 1;        // HFINTOSC
    CWG1CON0bits.EN = 1;

    __delay_us(100);
}

void usart_init() {
    TRISA5 = 1; // RA5 as RX input
    TRISA2 = 1; // RA2 as TX out
    ANSELA = 0;

    RXPPS  = 0b00101; // RX on RA5
    RA2PPS = 0b10100; // TX on RA2

    RC1STA  = 0b10010000; // SPEN=1, CREN=1
    TX1STA  = 0b00100100; // BRGH=1, TXEN=1, async
    BAUD1CON= 0b00001000; // BRG16=1
    SP1BRGH = 0;
    SP1BRGL = 68;         // 115200 baud @ Fosc settings
    TX9 = 1;              // 9-bit TX for parity-in-MSB
    RX9 = 1;              // 9-bit RX
    RCIE = 1;             // RX interrupt enable

    __delay_us(100);
}

uint8_t make_addr_byte(uint8_t start, uint8_t addr){
    // Make first/address byte for transmission (MSB=0 for address)
    uint8_t addr_byte = 0;
    addr_byte |= (start & 0b1);
    addr_byte |= (addr << 1);
    return addr_byte;
}

uint8_t getParity(uint8_t n) {
    // Return parity of n. If odd -> 1, even -> 0
    uint8_t p = 0;
    while (n) {
        p = !p;
        n = n & (n - 1);
    }
    return (p & 0b1);
}

void UART_Write(uint8_t data) {
    while(!TRMT){};
    TX9D   = (getParity(data) & 0b1);
    TX1REG = data;
}

void UART_processing(){
    if(getParity(buffer) != parity) return; // drop packet on wrong parity

    if((buffer >> 7) != 0b1){ // Address byte received (MSB=0)
        uint8_t addr  = (buffer >> 1);     // get address
        uint8_t start = (buffer & 0b1);    // get start/stop
        if(addr != 0){ // Not for this node — forward downstream
            state = 0;
            --addr; 
            UART_Write(make_addr_byte(start, addr));
            return;
        } else { // Addressed to this board
            state = start;
            if(start == 0){
                TMR2ON = 0;   // stop Timer2
                TRISA0 = 1;   // disable outputs
                TRISA1 = 1;
                duty_index = 0;
            }
            return;
        }
    } else { // Data byte received (MSB=1)
        if(state == 0){ // Not addressed — reflect back
            while(!TRMT){};
            TX9D   = parity & 0b1;
            TX1REG = buffer;
            return;
        } else {
            // Addressed to this board: unpack fields with new layout.
            TRISA1 = 0;
            TRISA0 = 0;

            // Start Timer2 (prescaler 1:4)
            T2CON  = 0b00000101;

            // [6:2]=duty (5 bits), [1:0]=freq (2 bits)
            freq_index = (buffer & FREQ_MASK);          // 0..3
            duty_index = (buffer & DUTY_MASK) >> 2;     // 0..31

            // Map duty index to 0..99
            duty_cycle = duty_cycle_lut_5bit[duty_index];

            // Load frequency
            PR2 = PR_val[freq_index];

            state = 0; // done with this transaction
            return;
        }
    }
}

void CCP_processing(){
    // Update CWG polarity windowing based on index within 0..199 frame
    if((index < duty_cycle) || (index >= 100 && index < (duty_cycle + 100))){
        if (cwg_flag == 0){
            // keep RA0 and RA1 opposite
            CWG1CON0bits.EN = 0;
            CWG1CON1bits.POLB = 0;
            CWG1CON0bits.EN = 1;
            cwg_flag = 1;
        }
    } else {
        if (cwg_flag == 1){
            // keep RA0 and RA1 the same
            CWG1CON0bits.EN = 0;
            CWG1CON1bits.POLB = 1;
            CWG1CON0bits.EN = 1;
            cwg_flag = 0;
        }
    }

    // Duty shaping via CCP registers: full or near-zero
    if(index < duty_cycle){
        if (duty_flag == 0){
            // full duty cycle
            CCPR1H = PR_val[freq_index];
            CCPR1L = 0x00;
            duty_flag = 1;
        }
    } else {
        if (duty_flag == 1){
            // near-zero duty cycle
            CCPR1H = 0x00;
            CCPR1L = 64;
            duty_flag = 0;
        }
    }
}

// Keep your 16-color palette, but map 32 duty steps -> 16 via a right shift.
void getColor(uint8_t duty_index_5bit, uint8_t color[3]) {
    uint8_t idx16 = (duty_index_5bit >> 1); // 0..31 -> 0..15
    if (idx16 > 15) idx16 = 15;

    switch (idx16) {
        case 0:  color[0] = 0;   color[1] = 0;   color[2] = 0;   break;  // Black
        case 1:  color[0] = 0;   color[1] = 32;  color[2] = 32;  break;  // Dark Teal
        case 2:  color[0] = 0;   color[1] = 64;  color[2] = 64;  break;  // Teal
        case 3:  color[0] = 0;   color[1] = 128; color[2] = 128; break;  // Cyan-Blue
        case 4:  color[0] = 0;   color[1] = 255; color[2] = 255; break;  // Cyan
        case 5:  color[0] = 0;   color[1] = 255; color[2] = 128; break;  // Light Greenish Cyan
        case 6:  color[0] = 0;   color[1] = 255; color[2] = 0;   break;  // Green
        case 7:  color[0] = 128; color[1] = 255; color[2] = 0;   break;  // Yellow-Green
        case 8:  color[0] = 255; color[1] = 255; color[2] = 0;   break;  // Yellow
        case 9:  color[0] = 255; color[1] = 128; color[2] = 0;   break;  // Orange
        case 10: color[0] = 255; color[1] = 0;   color[2] = 0;   break;  // Red
        case 11: color[0] = 255; color[1] = 0;   color[2] = 128; break;  // Pink
        case 12: color[0] = 255; color[1] = 0;   color[2] = 255; break;  // Bright Magenta
        case 13: color[0] = 128; color[1] = 0;   color[2] = 255; break;  // Magenta
        case 14: color[0] = 64;  color[1] = 0;   color[2] = 255; break;  // Purple
        case 15: color[0] = 255; color[1] = 255; color[2] = 255; break;  // White
        default: color[0] = 0;   color[1] = 0;   color[2] = 0;   break;
    }
}

// Timer2 Interrupt Service Routine
void __interrupt() ISR(void) {
    if (RCIF) {
        RCIF = 0;                 // Clear RX flag
        parity = RX9D;            // Read 9th parity bit
        buffer = RC1REG;          // Read data
        UART_processing();
        uart_recv_flag = 1;
    }
    else if(TMR2IF){
        TMR2IF = 0;
        index = index + 1;
        if(index == 200) index = 0;
        ccp_flag = 1;
    }
    else if(CCP1IF){
        CCP1IF = 0; // Clear CCP1 flag
    }
}

int main(int argc, char** argv) {

    init_ccp_cwg();
    usart_init();
    SPI_Init();
   
    // Infinite loop
    while(1) {
        if (uart_recv_flag) {
            uart_recv_flag = 0;
            // Update NeoPixel color when duty index changes
            if (color_index != duty_index){
                color_index = duty_index;
                getColor(duty_index, color);
                sendColor_SPI(color[0], color[1], color[2]);
            }
        }
        if(ccp_flag){
            CCP_processing();
            ccp_flag = 0;
        }
    }
}