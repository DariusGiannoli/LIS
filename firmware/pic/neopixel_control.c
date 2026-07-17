#include "neopixel_control.h"

void SPI_Init(void)
{
    SSP1ADD = 2;
    SSP1CON1 = 0b00101010;
    SSP1STAT = 0b00000000;

    TRISA4 = 0;
    RA4PPS = 0b11001;
}

void encodeByte(uint8_t inputByte, uint8_t outArray[4])
{
    uint8_t i;
    uint32_t encoded = 0;

    for (i = 0; i < 8; i++) {
        if (i % 2 == 0) {
            encoded <<= 2;
        }
        encoded <<= 3;
        encoded |= (inputByte & 0x80) ? WS2812_1 : WS2812_0;
        inputByte <<= 1;
    }

    outArray[0] = (uint8_t)((encoded >> 24) & 0xFF);
    outArray[1] = (uint8_t)((encoded >> 16) & 0xFF);
    outArray[2] = (uint8_t)((encoded >> 8) & 0xFF);
    outArray[3] = (uint8_t)(encoded & 0xFF);
}

void sendColor_SPI(uint8_t g, uint8_t r, uint8_t b)
{
    uint8_t gEncoded[4], rEncoded[4], bEncoded[4];
    uint8_t i;

    encodeByte(g, gEncoded);
    encodeByte(r, rEncoded);
    encodeByte(b, bEncoded);

    for (i = 0; i < NUM_BYTES_PER_COLOR; i++) {
        SSP1BUF = gEncoded[i];
        while (!SSP1STATbits.BF) {}
    }
    for (i = 0; i < NUM_BYTES_PER_COLOR; i++) {
        SSP1BUF = rEncoded[i];
        while (!SSP1STATbits.BF) {}
    }
    for (i = 0; i < NUM_BYTES_PER_COLOR; i++) {
        SSP1BUF = bEncoded[i];
        while (!SSP1STATbits.BF) {}
    }

    __delay_us(60);
}
