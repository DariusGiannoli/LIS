#include <stdio.h>
#include <stdlib.h>
#include "neopixel_control.h"

// PIC16F18313 Configuration Bit Settings

// CONFIG1
#pragma config FEXTOSC = OFF
#pragma config RSTOSC  = HFINT32   // HFINTOSC (1MHz)
#pragma config CLKOUTEN = OFF
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

#define _XTAL_FREQ  32000000

// Masks du data-byte (MSB=1) : [6:2]=duty(5b), [1:0]=freq(2b)
#define DUTY_MASK  0x7C
#define FREQ_MASK  0x03

uint8_t buffer = 0;
uint8_t parity = 0;        // 9e bit reçu (RX9D)
uint8_t uart_recv_flag = 0;

uint8_t duty_index = 0;    // 0..31
const uint8_t duty_cycle_lut_5bit[32] = {
    0, 0, 0, 1, 2, 3, 4, 5, 7, 8, 10, 13, 15, 18, 20, 23,
    27, 30, 34, 38, 42, 46, 50, 55, 60, 65, 70, 76, 82, 88, 94, 99
};
uint8_t duty_cycle = 0;

// 4 fréquences (2 bits)
uint8_t freq_index = 1;
const uint8_t PR_val[4] = {
    72,  // ~145 Hz
    52,  // ~200 Hz
    37,  // ~275 Hz
    27   // ~384 Hz
};

uint8_t ccp_flag = 0;
uint8_t cwg_flag = 0;
uint8_t duty_flag = 0;
uint8_t index = 0;
uint8_t state = 0; // 1 si la carte est "sélectionnée" (après START)

// Couleur neopixel (indicatif)
uint8_t color_index = 0;
uint8_t color[] = {0,0,0};

void init_ccp_cwg(void) {
    TRISA0 = 1;
    TRISA1 = 1;
    ANSELA = 0;
    WPUA   = 0;

    // PPS CWG -> RA1/RA0
    RA1PPS = 0b01000; // CWG1A
    RA0PPS = 0b01001; // CWG1B

    // CCP1 PWM (FMT=1)
    CCP1CON = 0b10011111;
    CCP1IE  = 1;

    GIE  = 1;
    PEIE = 1;

    TMR2IE = 1;

    // Timer2 prescaler 1:4, pas encore démarré
    T2CON = 0b00000001;
    PR2   = PR_val[freq_index];

    // CWG
    CWG1CON0 = 0b01000100; // half bridge, disable
    CWG1CON1 = 0;          // A non-inv, B inv
    CWG1DAT  = 0b00000011; // entrée depuis CCP1
    CWG1AS0  = 0b01111000;
    CWG1DBR  = 0;
    CWG1DBF  = 0;
    CWG1CLKCON = 1;        // HFINTOSC
    CWG1CON0bits.EN = 1;

    __delay_us(100);
}

void usart_init() {
    TRISA5 = 1; // RX
    TRISA2 = 1; // TX
    ANSELA = 0;

    RXPPS  = 0b00101; // RX sur RA5
    RA2PPS = 0b10100; // TX sur RA2

    RC1STA   = 0b10010000; // SPEN=1, CREN=1
    TX1STA   = 0b00100100; // BRGH=1, TXEN=1
    BAUD1CON = 0b00001000; // BRG16=1
    SP1BRGH  = 0;
    SP1BRGL  = 68;         // 115200 bauds @ Fosc configuré

    TX9 = 1;  // TX 9 bits (parité envoyée dans TX9D)
    RX9 = 1;  // RX 9 bits (parité lue dans RX9D)
    RCIE = 1; // interruption RX

    __delay_us(100);
}

uint8_t make_addr_byte(uint8_t start, uint8_t addr){
    uint8_t addr_byte = 0;
    addr_byte |= (start & 0b1);
    addr_byte |= (addr << 1);
    return addr_byte;
}

uint8_t getParity(uint8_t n) {
    // retourne parité(data): 1 si odd, 0 si even
    uint8_t p = 0;
    while (n) { p = !p; n = n & (n - 1); }
    return (p & 0b1);
}

void UART_Write(uint8_t data) {
    while(!TRMT){};
    // EVEN parity : TX9D = parity(data)
    TX9D   = (getParity(data) & 0b1);
    TX1REG = data;
}

void UART_processing(){
    // Vérif parité (even). Si ESP n'est pas en 8E1, ça va tout dropper !
    if(getParity(buffer) != parity) return;

    if((buffer >> 7) != 0b1){ // octet d'adresse (MSB=0)
        uint8_t addr  = (buffer >> 1);
        uint8_t start = (buffer & 0b1);
        if(addr != 0){
            state = 0;
            --addr;
            UART_Write(make_addr_byte(start, addr));
            return;
        } else {
            state = start;
            if(start == 0){
                TMR2ON = 0;
                TRISA0 = 1;
                TRISA1 = 1;
                duty_index = 0;
            }
            return;
        }
    } else { // data (MSB=1)
        if(state == 0){
            while(!TRMT){};
            TX9D   = parity & 0b1;
            TX1REG = buffer;
            return;
        } else {
            TRISA1 = 0;
            TRISA0 = 0;
            T2CON  = 0b00000101; // start TMR2 (1:4)

            // [6:2]=duty(5b), [1:0]=freq(2b)
            freq_index = (buffer & FREQ_MASK);           // 0..3
            duty_index = (buffer & DUTY_MASK) >> 2;      // 0..31

            duty_cycle = duty_cycle_lut_5bit[duty_index];
            PR2 = PR_val[freq_index];

            state = 0;
            return;
        }
    }
}

void CCP_processing(){
    // Fenêtrage CWG sur index 0..199
    if((index < duty_cycle) || (index >= 100 && index < (duty_cycle + 100))){
        if (cwg_flag == 0){
            CWG1CON0bits.EN = 0;
            CWG1CON1bits.POLB = 0; // A/B opposés
            CWG1CON0bits.EN = 1;
            cwg_flag = 1;
        }
    } else {
        if (cwg_flag == 1){
            CWG1CON0bits.EN = 0;
            CWG1CON1bits.POLB = 1; // A/B identiques
            CWG1CON0bits.EN = 1;
            cwg_flag = 0;
        }
    }

    // Amplitude via CCP (plein / quasi-nul)
    if(index < duty_cycle){
        if (duty_flag == 0){
            CCPR1H = PR_val[freq_index];
            CCPR1L = 0x00;
            duty_flag = 1;
        }
    } else {
        if (duty_flag == 1){
            CCPR1H = 0x00;
            CCPR1L = 64;
            duty_flag = 0;
        }
    }
}

// Palette existante (16 couleurs) : map 32 -> 16
void getColor(uint8_t duty_index_5bit, uint8_t color[3]) {
    uint8_t idx16 = (duty_index_5bit >> 1);
    if (idx16 > 15) idx16 = 15;
    switch (idx16) {
        case 0:  color[0]=0;   color[1]=0;   color[2]=0;   break;
        case 1:  color[0]=0;   color[1]=32;  color[2]=32;  break;
        case 2:  color[0]=0;   color[1]=64;  color[2]=64;  break;
        case 3:  color[0]=0;   color[1]=128; color[2]=128; break;
        case 4:  color[0]=0;   color[1]=255; color[2]=255; break;
        case 5:  color[0]=0;   color[1]=255; color[2]=128; break;
        case 6:  color[0]=0;   color[1]=255; color[2]=0;   break;
        case 7:  color[0]=128; color[1]=255; color[2]=0;   break;
        case 8:  color[0]=255; color[1]=255; color[2]=0;   break;
        case 9:  color[0]=255; color[1]=128; color[2]=0;   break;
        case 10: color[0]=255; color[1]=0;   color[2]=0;   break;
        case 11: color[0]=255; color[1]=0;   color[2]=128; break;
        case 12: color[0]=255; color[1]=0;   color[2]=255; break;
        case 13: color[0]=128; color[1]=0;   color[2]=255; break;
        case 14: color[0]=64;  color[1]=0;   color[2]=255; break;
        case 15: color[0]=255; color[1]=255; color[2]=255; break;
        default: color[0]=0;   color[1]=0;   color[2]=0;   break;
    }
}

void __interrupt() ISR(void) {
    if (RCIF) {
        RCIF = 0;
        parity = RX9D;
        buffer = RC1REG;
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
        CCP1IF = 0;
    }
}

int main(int argc, char** argv) {
    init_ccp_cwg();
    usart_init();
    SPI_Init();

    while(1) {
        if (uart_recv_flag) {
            uart_recv_flag = 0;
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