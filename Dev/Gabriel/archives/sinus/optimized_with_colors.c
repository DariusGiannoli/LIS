/*  main.c — PIC16F18313
 *  True-sine (Timer1 + 64-pt LUT) + duty 5 bits (0..31, gamma→0..99)
 *  Colors: 16 key colors + interpolation → 32 steps (0..31)
 *  Protocol unchanged: START: addr + duty5 + freq3 ; STOP: addr
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

// ================== Protocol / state ==================
static volatile uint8_t buffer = 0;
static volatile uint8_t uart_recv_flag = 0;

static volatile uint8_t duty_cycle = 0;   // 0..99 (from duty5 via gamma)
static volatile uint8_t duty_index  = 0;  // 0..31 (for color mapping)
static volatile uint8_t freq_index  = 3;  // 0..7

// Mechanical frequency table (Hz) for indices 0..7
static const uint16_t FREQ_HZ[8] = {123, 145, 170, 200, 235, 275, 322, 384};

// FSM
static volatile uint8_t state = 0;        // 0 idle, 1 wait duty, 2 wait freq
static volatile uint8_t temp_duty5 = 0;   // 0..31

// LED
static uint8_t color_index = 0;
static uint8_t color[3]    = {0,0,0};

// ================== True-sine engine (Timer1 + PWM 40 kHz) ==================
#define SINE_LEN   64u                // 64 samples / period
#define SINE_PEAK  1023u
#define CCP1_PPS   0x0C               // PPS code for CCP1 on PIC16F18313
#define MIN_DRIVE_TICKS 2u            // anti-buzz near zero

// Quarter-wave LUT (0..90°), 17 points (0..16)
static const uint16_t SINE_QW[17] = {
      0, 100, 200, 298, 392, 482, 568, 649, 723,
    791, 850, 902, 945, 979,1003,1018,1023
};

// Engine internal state
static volatile uint8_t  phase_idx = 0;   // 0..63
static volatile int8_t   last_sign = 0;   // -1 / +1
static volatile uint16_t t1_reload = 0;   // Timer1 reload (1 µs ticks)
static volatile uint16_t duty_max  = 0;   // 799 (PR2=199, right-aligned)
static volatile uint16_t scale     = 0;   // (duty_max * amp%)/100

// ---------- helpers: PWM & routing ----------
static inline void set_pwm10(uint16_t d){ CCPR1H = d >> 8; CCPR1L = d & 0xFF; }

// disconnect CCP1 and drive low (coast)
static inline void coast_both(void){
    RA1PPS = 0; LATAbits.LATA1 = 0;
    RA0PPS = 0; LATAbits.LATA0 = 0;
}

// route half-cycle: + → RA1=1, PWM on RA0 ; − → RA0=1, PWM on RA1
static inline void route_halfcycle(int8_t sign){
    if (sign > 0){ LATAbits.LATA1 = 1; RA0PPS = CCP1_PPS; } // positive
    else          { LATAbits.LATA0 = 1; RA1PPS = CCP1_PPS; } // negative
}

// sample full sine at index i (0..63) from quarter-wave table
static inline int16_t sine64_sample(uint8_t i){
    if (i <= 16) {
        return (int16_t)SINE_QW[i];
    } else if (i <= 32) {
        return (int16_t)SINE_QW[32 - i];
    } else if (i <= 48) {
        return -(int16_t)SINE_QW[i - 32];
    } else {
        return -(int16_t)SINE_QW[64 - i];
    }
}

// Timer1: Fs = freq_hz * SINE_LEN ; T1 prescaler 1:8 => 1 µs tick
static void t1_set_freq(uint16_t freq_hz){
    if (freq_hz == 0) freq_hz = 1;
    uint32_t Fs = (uint32_t)freq_hz * (uint32_t)SINE_LEN; // samples per second
    // ticks_per_sample = round(1e6 / Fs)
    uint32_t ticks_per_sample = (1000000ul + (Fs/2)) / Fs;
    if (ticks_per_sample < 5)       ticks_per_sample = 5;
    if (ticks_per_sample > 60000ul) ticks_per_sample = 60000ul;
    t1_reload = (uint16_t)(65536ul - ticks_per_sample);

    T1CONbits.TMR1ON = 0;
    TMR1H = (uint8_t)(t1_reload >> 8);
    TMR1L = (uint8_t)(t1_reload & 0xFF);
    PIR1bits.TMR1IF = 0;
    T1CONbits.TMR1ON = 1;
}

// Amplitude in percent (0..100)
static inline void lra_set_amp(uint8_t amp_pct){
    if (amp_pct > 100) amp_pct = 100;
    scale = (uint16_t)((uint32_t)duty_max * amp_pct / 100u);
    if (scale == 0u){
        coast_both();
        set_pwm10(0);
    }
}

// Init PWM (40 kHz) + Timer1 (stopped until START)
static void lra_init(void){
    // GPIO
    ANSELA = 0x00;
    TRISAbits.TRISA1 = 0;
    TRISAbits.TRISA0 = 0;
    coast_both();

    // PWM 40 kHz (Timer2, Fosc/4 = 8 MHz)
    PR2 = 199;                                // 8 MHz / (199+1) = 40 kHz ticks
    duty_max = (uint16_t)((PR2 + 1u) * 4u - 1u); // 799 (right-aligned)
    T2CON = 0; T2CONbits.T2CKPS = 0b00; T2CONbits.TMR2ON = 1;
    PIR1bits.TMR2IF = 0; while(!PIR1bits.TMR2IF); PIR1bits.TMR2IF = 0;

    // CCP1 PWM right-aligned
    CCP1CON = 0b10001111;
    set_pwm10(0);

    // Timer1 @ 1 µs tick (Fosc/4 + prescale 1:8)
    T1CON = 0; T1CONbits.T1CKPS = 0b11; // 1:8
    // don't start yet; t1_set_freq() will

    // Interrupts
    PIE1bits.TMR1IE = 1;
    INTCONbits.PEIE = 1;
    INTCONbits.GIE  = 1;

    // Sine state
    phase_idx = 0; last_sign = 0; scale = 0;
    coast_both();
}

// ===== Gamma mapping 5-bit (0..31) → 0..99 (more resolution at low levels) =====
static inline uint8_t map5bit_to_0_99_gamma(uint8_t v){
    if (v > 31u) v = 31u;
    // x = v*8 (0..248); g ≈ x^2 / 255 (soft non-linearity ~ gamma 1.2)
    uint16_t x = (uint16_t)v * 8u;                   // 0..248
    uint16_t g = (uint16_t)((x * x + 127u) / 255u);  // 0..241 approx
    uint16_t pct = (uint16_t)((g * 99u + 64u) / 128u); // 0..99
    return (uint8_t)pct;
}

// ================== UART protocol (unchanged PC/ESP side) ==================
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
    // MSB=0 -> Address
    if ((buffer >> 7) == 0){
        uint8_t addr  = (buffer >> 1);
        uint8_t start = (buffer & 0x1u);

        if (addr != 0){
            state = 0;
            --addr;
            UART_Write(make_addr_byte(start, addr)); // forward along chain
            return;
        }else{
            if (start == 0){
                // STOP: stop Timer1, coast, zero amplitude
                state = 0;
                T1CONbits.TMR1ON = 0;
                coast_both();
                set_pwm10(0);
                duty_cycle = 0;
                duty_index = 0;
            }else{
                // START -> expect DUTY (5 bits)
                state = 1;
            }
            return;
        }
    }
    // MSB=1 -> Data
    else {
        switch(state){
            case 0:
                UART_Write(buffer); // forward raw if not for us
                break;

            case 1: // DUTY5 (0..31)
                temp_duty5 = (uint8_t)(buffer & 0x1Fu);
                state = 2;
                break;

            case 2: // FREQ3 (0..7)
            {
                freq_index = (uint8_t)(buffer & 0x07u);

                // Map duty with gamma, set amplitude
                duty_cycle = map5bit_to_0_99_gamma(temp_duty5); // 0..99
                if (duty_cycle > 99u) duty_cycle = 99u;
                lra_set_amp(duty_cycle);                        // amplitude %

                // Start/adjust mechanical frequency
                uint16_t f = FREQ_HZ[freq_index];
                t1_set_freq(f);

                // reset phase for neat start
                phase_idx = 0;
                last_sign = 0;

                // === COLOR INDEX (0..31) aligned with duty5 ===
                duty_index = temp_duty5; // direct 0..31

                state = 0;
            } break;

            default:
                state = 0;
                break;
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

// ================== ISR ==================
void __interrupt() ISR(void){
    if (RCIF){
        // Robust UART (optional)
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

        // next phase
        uint8_t i = phase_idx + 1u;
        if (i >= SINE_LEN) i = 0;
        phase_idx = i;

        int16_t s = sine64_sample(i);
        int8_t  sign = (s > 0) ? +1 : ((s < 0) ? -1 : last_sign);

        if (scale == 0u){
            coast_both();
            set_pwm10(0);
            last_sign = sign;
            return;
        }

        // Zero-cross: clean reroute
        if (sign != last_sign){
            coast_both();
            route_halfcycle(sign);
            last_sign = sign;
        }

        // amplitude -> duty (fixed-point)
        uint16_t mag = (uint16_t)(s >= 0 ? s : -s); // 0..1023
        uint32_t tmp = (uint32_t)scale * (uint32_t)mag + 512u;
        uint16_t duty_forward = (uint16_t)(tmp >> 10);

        if (duty_forward <= MIN_DRIVE_TICKS){
            set_pwm10(duty_max);                 // quiet near zero
        }else{
            uint16_t duty_inv = (uint16_t)(duty_max - duty_forward);
            set_pwm10(duty_inv);                 // active-low PWM
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
                color_index = duty_index;              // 0..31
                getColor32(color_index, color);

                // === CRITICAL SECTION: disable interrupts during WS2812 send ===
                uint8_t gie = INTCONbits.GIE;         // save global interrupt enable
                INTCONbits.GIE = 0;                   // disable all interrupts
                // (option granulaire: couper seulement TMR1IE)
                // uint8_t t1ie = PIE1bits.TMR1IE; PIE1bits.TMR1IE = 0;

                sendColor_SPI(color[0], color[1], color[2]);

                // restore interrupts
                // PIE1bits.TMR1IE = t1ie;
                INTCONbits.GIE = gie;
            }
        }
        // all real-time work is done in ISRs
    }
    return 0;
}