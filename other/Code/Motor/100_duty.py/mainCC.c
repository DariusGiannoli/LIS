/* 
 * File:   main_fixed.c
 * Author: MasonC (modified)
 *
 * Created on November 8, 2022, 10:19 PM
 * Updated to enable PWM outputs and Timer2 on Start
 */

#include <xc.h>
#include <stdint.h>
#include <stdlib.h>
#include "neopixel_control.h"

// PIC16F18313 Configuration Bit Settings
#pragma config FEXTOSC = OFF    // External Oscillator disabled
#pragma config RSTOSC  = HFINT32// Power-up default HFINTOSC@1MHz
#pragma config CLKOUTEN= OFF    // CLKOUT function disabled
#pragma config CSWEN   = OFF    // Oscillator NOSC/NDIV locked
#pragma config FCMEN   = OFF    // Fail-Safe Clock Monitor disabled
#pragma config MCLRE   = ON     // MCLR pin enabled
#pragma config PWRTE   = OFF    // Power-up Timer disabled
#pragma config WDTE    = OFF    // Watchdog Timer disabled
#pragma config LPBOREN = OFF    // Low-power BOR disabled
#pragma config BOREN   = OFF    // Brown-out Reset disabled
#pragma config BORV    = LOW    // BOR voltage 2.45V
#pragma config PPS1WAY = OFF    // PPSLOCK can be set/cleared repeatedly
#pragma config STVREN  = ON     // Stack Overflow/Underflow Reset enabled
#pragma config DEBUG   = OFF    // Background debugger disabled
#pragma config WRT     = OFF    // Flash write protection off
#pragma config LVP     = OFF    // Low-voltage programming disabled
#pragma config CP      = OFF    // Code protection off
#pragma config CPD     = OFF    // Data memory protection off

#define _XTAL_FREQ  32000000UL

// Commands
enum { CMD_COUNT_REQUEST = 0xFE, CMD_COUNT_RESPONSE = 0xFD };

// UART globals
volatile uint8_t buffer = 0;
volatile uint8_t parity = 0;
volatile uint8_t uart_recv_flag = 0;

// Data decoding
enum { STAGE_ADDR=0, STAGE_DATA1, STAGE_DATA2 };
uint8_t data_stage = 0;
uint8_t data1 = 0;

// PWM/haptics globals
uint8_t duty_index = 0;            // 0-99
uint8_t duty_cycle = 0;
const uint8_t duty_cycle_array[] = {0,7,14,21,28,35,42,49,56,63,69,76,83,90,95,99};
uint8_t freq_index = 3;            // 0-7
const uint8_t PR_val[] = {85,72,60,52,44,37,32,27};

uint8_t ccp_flag = 0;
uint8_t cwg_flag = 0;
uint8_t duty_flag = 0;
uint8_t index = 0;
uint8_t state = 0;

// Neopixel color
enum { PALETTE_SIZE=16 };
uint8_t color_index = 0;
uint8_t color[3] = {0,0,0};
static const uint8_t palette[PALETTE_SIZE][3] = {
    {0,0,0},{0,32,32},{0,64,64},{0,128,128},
    {0,255,255},{0,255,128},{0,255,0},{128,255,0},
    {255,255,0},{255,128,0},{255,0,0},{255,0,128},
    {255,0,255},{128,0,255},{64,0,255},{255,255,255}
};

// Counting mode
typedef uint8_t bool_t;
volatile uint8_t count_mode = 0;
volatile uint8_t count_timeout = 0;
volatile uint8_t my_address = 0;

// Function prototypes
void init_ccp_cwg(void);
void usart_init(void);
uint8_t getParity(uint8_t n);
void UART_Write(uint8_t data);
void UART_processing(void);
void CCP_processing(void);
void getColor(uint8_t duty, uint8_t col[3]);

//------------------------------------------------------------------------------
void init_ccp_cwg(void) {
    // Configure RA0, RA1 as outputs for PWM/CWG
    TRISA0 = 0;
    TRISA1 = 0;
    ANSELA = 0;
    WPUA   = 0;
    RA1PPS = 0b01000;  // CWG1A
    RA0PPS = 0b01001;  // CWG1B

    // CCP1 in PWM mode (FMT=1)
    CCP1CON = 0b10011111;
    CCP1IE  = 1;

    // Timer2: prescaler 1:4, TMR2ON=1
    T2CON = 0b10000001;
    PR2   = PR_val[freq_index];
    TMR2IE = 1;

    // CWG1 half-bridge
    CWG1CON0 = 0b01000100;
    CWG1CON1 = 0;
    CWG1DAT  = 0b00000011;
    CWG1AS0  = 0b01111000;
    CWG1DBR  = 0;
    CWG1DBF  = 0;
    CWG1CLKCON = 1;
    CWG1CON0bits.EN = 1;

    // Global/Peripheral interrupts
    GIE  = 1;
    PEIE = 1;
    __delay_us(100);
}

//------------------------------------------------------------------------------
void usart_init(void) {
    // RX: RA5, TX: RA2
    TRISA5 = 1;
    TRISA2 = 1;
    ANSELA = 0;
    RXPPS  = 0b00101;  // RA5->RX
    RA2PPS = 0b10100;  // TX->RA2

    // 9-bit UART, 115200 8E1
    RC1STA  = 0b10010000;
    TX1STA  = 0b00100100;
    BAUD1CON= 0b00001000;
    SP1BRGH = 0;
    SP1BRGL = 68;
    RX9     = 1;
    TX9     = 1;
    RCIE    = 1;
    __delay_us(100);
}

//------------------------------------------------------------------------------
uint8_t getParity(uint8_t n) {
    uint8_t p=0;
    while(n) { p = !p; n &= (n-1); }
    return p;
}

void UART_Write(uint8_t data) {
    while(!TRMT);
    TX9D   = getParity(data);
    TX1REG = data;
}

//------------------------------------------------------------------------------
void UART_processing(void) {
    // Check 9th-bit parity
    if (getParity(buffer) != parity) return;

    // COUNT MODE
    if (buffer == CMD_COUNT_REQUEST) {
        count_mode = 1;
        count_timeout = 200;
        my_address = 0;
        UART_Write(CMD_COUNT_REQUEST);
        return;
    }
    if (buffer == CMD_COUNT_RESPONSE) {
        if (count_mode) {
            my_address++;
            UART_Write(CMD_COUNT_RESPONSE);
            count_mode = 0;
        } else {
            UART_Write(CMD_COUNT_RESPONSE);
        }
        return;
    }
    if (count_mode && count_timeout == 0) {
        my_address = 0;
        UART_Write(CMD_COUNT_RESPONSE);
        count_mode = 0;
        return;
    }

    // ADDRESS vs DATA (MSB of buffer)
    if ((buffer & 0x80) == 0) {

        // Address byte (bit7=0)
        uint8_t addr   = (buffer >> 1) & 0x3F;
        uint8_t startF = buffer & 0x01;
        data_stage = STAGE_ADDR;

        if (addr == my_address) {
            // addressed to me
            state = startF;
            if (startF) {
                // START: enable PWM outputs and Timer2
                TRISA0 = 0;
                TRISA1 = 0;
                TMR2ON = 1;
            } else {
                // STOP
                TMR2ON = 0;
                TRISA0 = 1;
                TRISA1 = 1;
                duty_index = 0;
            }
        } else if (addr > 0) {
            // forward to next hop
            state = 0;
            addr--;
            UART_Write((addr<<1)|startF);
        }
        return;
    }

    // Data bytes (bit7=1)
    if (state == 0) {
        // not for me ? forward
        UART_Write(buffer);
        data_stage = STAGE_ADDR;
        return;
    }

    // state==1: consume two data bytes
    if (data_stage == STAGE_ADDR) {
        data1 = buffer;
        data_stage = STAGE_DATA1;
        return;
    } else {
        uint8_t data2 = buffer;
        data_stage = STAGE_ADDR;

        // decode fields
        uint8_t low = (data1 >> 3) & 0x1F;
        uint8_t high = data2 & 0x07;
        duty_index = (high<<5) | low;
        if (duty_index > 99) duty_index = 99;
        duty_cycle = duty_index;

        freq_index = (data2 >> 3) & 0x07;
        PR2 = PR_val[freq_index];

        state = 0;
        return;
    }
}



//------------------------------------------------------------------------------
void CCP_processing(void) {
    // CWG toggle
    if ((index < duty_cycle) || (index >= 100 && index < duty_cycle+100)) {
        if (!cwg_flag) {
            CWG1CON0bits.EN=0;
            CWG1CON1bits.POLB=0;
            CWG1CON0bits.EN=1;
            cwg_flag=1;
        }
    } else {
        if (cwg_flag) {
            CWG1CON0bits.EN=0;
            CWG1CON1bits.POLB=1;
            CWG1CON0bits.EN=1;
            cwg_flag=0;
        }
    }
    // CCP1 duty
    if (index < duty_cycle) {
        if (!duty_flag) {
            CCPR1H = PR_val[freq_index];
            CCPR1L = 0;
            duty_flag=1;
        }
    } else {
        if (duty_flag) {
            CCPR1H=0;
            CCPR1L=64;
            duty_flag=0;
        }
    }
}

//------------------------------------------------------------------------------
void getColor(uint8_t duty, uint8_t col[3]) {
    if (duty > 100) duty=100;
    uint8_t idx = (duty * (PALETTE_SIZE-1) + 50) / 100;
    col[0]=palette[idx][0];
    col[1]=palette[idx][1];
    col[2]=palette[idx][2];
}

//------------------------------------------------------------------------------
void __interrupt() ISR(void) {
    if (RCIF) {
        RCIF=0;
        parity = RX9D;
        buffer = RC1REG;
        UART_processing();
        uart_recv_flag=1;
    } else if (TMR2IF) {
        TMR2IF=0;
        if (++index >= 200) index=0;
        ccp_flag=1;
        if (count_mode && count_timeout>0) count_timeout--;
    } else if (CCP1IF) {
        CCP1IF=0;
    }
}

int main(void) {
    init_ccp_cwg();
    usart_init();
    SPI_Init(); 
    
    TRISA0 = 0;
    TRISA1 = 0;
    TMR2ON = 1;
    
    duty_cycle = 100;
    duty_index = 100;
    
    freq_index = 2;
    PR2 = PR_val[freq_index];
    
    
    
   
    while (1) {
        if (uart_recv_flag) {
            uart_recv_flag=0;
            if (color_index!=duty_index) {
                color_index=duty_index;
                getColor(duty_index,color);
                sendColor_SPI(color[0],color[1],color[2]);
            }
        }
        if (ccp_flag) {
            CCP_processing();
            ccp_flag=0;
        }
    }
    return 0;
}