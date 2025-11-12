/*  main.c — PIC16F18313 @ 32 MHz (XC8)
 *  Protocole ESP→PIC (3 octets) :
 *    B0 (MSB=0) : [addr6<<1 | start]  (start=1 → START, 0 → STOP)
 *    B1 (MSB=1) : [1 D4 D3 D2 D1 D0 0 0]      => duty5 = b & 0x1F
 *    B2 (MSB=1) : [1 0 0  W  F2 F1 F0]        => wave = (b>>3)&1, freq = b&7
 *
 *  wave=1 : SINE (implémentation de base) — PWM via CCP1, amplitude LUT
 *  wave=0 : SQUARE (corrigé) — fenêtrage + inversion d’orientation à mi-cycle
 *  duty5 (0..31) → duty_pct 0..99 ; LED index 0..31 (32 couleurs)
 */

#include <xc.h>
#include <stdint.h>
#include "neopixel_control.h"

#define _XTAL_FREQ 32000000UL

//==================== Config Bits ====================
#pragma config FEXTOSC=OFF, RSTOSC=HFINT32, CLKOUTEN=OFF, CSWEN=OFF, FCMEN=OFF
#pragma config MCLRE=ON, PWRTE=OFF, WDTE=OFF, LPBOREN=OFF, BOREN=OFF, BORV=LOW, PPS1WAY=OFF, STVREN=ON, DEBUG=OFF
#pragma config WRT=OFF, LVP=OFF, CP=OFF, CPD=OFF

//==================== État global ====================
static volatile uint8_t rx_state = 0;      // 0: attend addr, 1: duty, 2: wave+freq
static volatile uint8_t duty5_raw = 0;     // 0..31 (LED)
static volatile uint8_t duty_pct  = 0;     // 0..99 (actuation)
static volatile uint8_t wave_mode = 0;     // 0=square, 1=sine
static volatile uint8_t freq_index= 3;     // 0..7

static volatile uint8_t index200  = 0;     // 0..199 (2 demi-périodes de 100 “ticks”)
static volatile uint8_t ccp_flag  = 0;
static volatile uint8_t duty_flag = 0;
static volatile uint8_t cwg_flag  = 0;
static volatile uint8_t last_half = 0xFF;

static uint8_t color_index = 0;
static uint8_t color[3]    = {0,0,0};

static const uint8_t PR_val[8] = {85, 72, 60, 52, 44, 37, 32, 27}; // porteuse

//==================== LUT SINE (64 pts demi-sinus 0..99) ====================
static const uint8_t SINE64[64] = {
     0,  2,  5,  7, 10, 12, 15, 18,
    20, 23, 26, 28, 31, 34, 36, 39,
    42, 44, 47, 50, 52, 55, 57, 60,
    62, 65, 67, 69, 72, 74, 76, 79,
    81, 83, 85, 87, 89, 91, 93, 95,
    96, 97, 98, 99, 99, 99, 98, 97,
    96, 95, 93, 91, 89, 87, 85, 83,
    81, 79, 76, 74, 72, 69, 67, 65
};

// pos 0..99 → amplitude 0..99 (interpolation simple, coût réduit)
static inline uint8_t sine_amp_0_99(uint8_t pos){
    uint16_t p = (uint16_t)pos * 63u;         // /99 plus bas → léger
    uint8_t  i = (uint8_t)(p / 99u);
    uint8_t  r = (uint8_t)(p % 99u);
    uint8_t  a = SINE64[i];
    uint8_t  b = (i < 63) ? SINE64[i+1] : SINE64[63];
    int16_t  d = (int16_t)b - (int16_t)a;
    uint16_t interp = ((uint16_t)d * r + 50u) / 99u;
    uint16_t out = (uint16_t)a + interp;
    return (out > 99u) ? 99u : (uint8_t)out;
}

//==================== Helpers ====================
static inline uint8_t map5bit_to_0_99(uint8_t v){
    if(v > 31u) v = 31u;
    return (uint8_t)(((uint16_t)v * 99u + 15u) / 31u); // arrondi, 16-bit
}

static inline uint8_t make_addr_byte(uint8_t start, uint8_t addr6){
    return (uint8_t)((addr6 & 0x3Fu) << 1) | (start & 1u);
}

//==================== LED 32 couleurs ====================
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

//==================== Init périphériques ====================
static void init_ccp_cwg(void){
    ANSELA=0; WPUA=0;

    // CWG sur RA1(A) et RA0(B)
    TRISA1=1; TRISA0=1;
    RA1PPS=0b01000;          // CWG1A
    RA0PPS=0b01001;          // CWG1B

    // CCP1 PWM (FMT=1)
    CCP1CON=0b10011111;      // CCP1M=1111 PWM, FMT=1
    // Timer2 (porteuse)
    T2CON=0b00000001;        // TMR2ON=0, CKPS=1:1 (on passera en 1:4 au START)
    PR2=PR_val[freq_index];
    TMR2=0; TMR2IF=0; TMR2IE=1;

    // CWG half-bridge
    CWG1CON0=0b01000100;     // MODE=01 (half-bridge), LD=1, EN=0 (sera mis à 1)
    CWG1CON1=0;              // POLA=0, POLB=0
    CWG1DAT=0b00000011;      // source = CCP1
    CWG1AS0=0b01111000;      // shutdown config
    CWG1DBR=0; CWG1DBF=0;
    CWG1CLKCON=1;            // HFINTOSC
    CWG1CON0bits.EN=1;

    PEIE=1; GIE=1;
    __delay_us(100);
}

static void usart_init(void){
    TRISA5=1; TRISA2=1; ANSELA=0;
    RXPPS=0b00101;          // RA5 -> RX
    RA2PPS=0b10100;         // TX  -> RA2

    RC1STA=0b10010000;      // SPEN=1, CREN=1
    TX1STA=0b00100100;      // BRGH=1, TXEN=1
    BAUD1CON=0b00001000;    // BRG16=1
    SP1BRGH=0; SP1BRGL=68;  // 115200 @32MHz

    RCIF=0; RCIE=1;
    __delay_us(100);
}

//==================== START/STOP ====================
static void apply_STOP(void){
    TMR2ON=0;
    TRISA0=1; TRISA1=1;     // tri-state sorties
    duty_pct=0;
    last_half=0xFF;
    duty_flag=0; cwg_flag=0;
}

static void apply_START_and_settings(void){
    TRISA1=0; TRISA0=0;     // enable sorties
    PR2 = PR_val[freq_index];
    T2CON=0b00000101;       // CKPS=1:4, TMR2ON=1
    TMR2=0;
    duty_flag=0; cwg_flag=0; last_half=0xFF;
}

//==================== UART parsing ====================
static inline void forward_byte(uint8_t b){ while(!TRMT){} TX1REG=b; }

static void UART_processing(uint8_t b){
    if((b>>7)==0){ // ADDR (MSB=0)
        uint8_t addr6=(b>>1)&0x3F;
        uint8_t start=b&1u;
        if(addr6!=0){
            forward_byte(make_addr_byte(start, (uint8_t)(addr6-1)));
            rx_state=0;
            return;
        }else{
            if(start==0){ apply_STOP(); rx_state=0; }
            else         { rx_state=1; }
            return;
        }
    }else{ // DATA (MSB=1)
        if(rx_state==0){
            forward_byte(b);
            return;
        }else if(rx_state==1){
            duty5_raw = (uint8_t)(b & 0x1Fu); // 0..31
            rx_state  = 2;
            return;
        }else{ // rx_state==2
            wave_mode = (uint8_t)((b>>3)&0x01u);
            freq_index= (uint8_t)(b & 0x07u);
            if(freq_index>7) freq_index=7;

            duty_pct = map5bit_to_0_99(duty5_raw);
            apply_START_and_settings();

            // LED
            if(color_index!=duty5_raw){
                color_index=duty5_raw;
                getColor32(color_index, color);
                sendColor_SPI(color[0], color[1], color[2]);
            }
            rx_state=0;
            return;
        }
    }
}

//==================== Square (orientation flip) ====================
static void square_processing(void){
    uint8_t half = (index200 >= 100); // 0/1
    uint8_t on =
        (index200 < duty_pct) ||
        (index200 >= 100 && index200 < (uint8_t)(100 + duty_pct));

    if(on){
        // orientation ± selon demi-période
        if(cwg_flag==0 || last_half!=half){
            CWG1CON0bits.EN=0;
            if(!half){
                // demi 1 : A non-inverti, B “opposé”
                CWG1CON1bits.POLA=0;
                CWG1CON1bits.POLB=0;
            }else{
                // demi 2 : orientation inverse
                CWG1CON1bits.POLA=1;
                CWG1CON1bits.POLB=1;
            }
            CWG1CON0bits.EN=1;
            cwg_flag=1; last_half=half;
        }
        // PWM porteur quasi 100%
        if(duty_flag==0){
            CCPR1H=PR_val[freq_index];
            CCPR1L=0x00;
            duty_flag=1;
        }
    }else{
        // “coast” : sorties identiques (pas de diff)
        if(cwg_flag==1){
            CWG1CON0bits.EN=0;
            CWG1CON1bits.POLA=0;
            CWG1CON1bits.POLB=1;
            CWG1CON0bits.EN=1;
            cwg_flag=0;
        }
        if(duty_flag==1){
            CCPR1H=0x00; CCPR1L=64; // petit filet
            duty_flag=0;
        }
    }
}

//==================== Sine (base) ====================
static void sine_processing(void){
    uint8_t half = (index200 >= 100);
    uint8_t pos  = (half ? (uint8_t)(199 - index200) : index200); // 0..99
    uint8_t lut  = sine_amp_0_99(pos);                            // 0..99
    uint16_t amp = ((uint16_t)lut * (uint16_t)duty_pct + 50u) / 99u; // 0..99

    // change d’orientation (avec EN toggle — version “base”)
    if (cwg_flag==0 || last_half!=half){
        CWG1CON0bits.EN=0;
        if (!half){ CWG1CON1bits.POLA=0; CWG1CON1bits.POLB=0; }
        else      { CWG1CON1bits.POLA=1; CWG1CON1bits.POLB=1; }
        CWG1CON0bits.EN=1;
        cwg_flag=1; last_half=half;
    }

    // PWM: duty ≈ amp/99 de PR2 (8-bit via CCPR1H), simple et léger
    uint16_t pr   = PR_val[freq_index];
    uint16_t dcnt = (amp >= 99u) ? pr : (uint16_t)((pr * amp + 50u) / 99u);
    if (dcnt > 255u) dcnt = 255u;

    CCPR1H = (uint8_t)dcnt;
    CCPR1L = 0x00;
    duty_flag = 1;
}

//==================== IT ====================
void __interrupt() ISR(void){
    if(RCIF){
        RCIF=0;
        UART_processing(RC1REG);
    }else if(TMR2IF){
        TMR2IF=0;
        index200++; if(index200>=200u) index200=0u;
        ccp_flag=1;
    }
}

//==================== Main ====================
int main(void){
    init_ccp_cwg();
    usart_init();
    SPI_Init();

    apply_STOP();

    for(;;){
        if(ccp_flag){
            ccp_flag=0;
            if(TMR2ON){
                if(wave_mode) sine_processing();
                else          square_processing();
            }
        }
    }
    return 0;
}