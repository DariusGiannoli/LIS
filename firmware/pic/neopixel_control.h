#ifndef NEOPIXEL_CONTROL_H
#define NEOPIXEL_CONTROL_H

#include <xc.h>
#include <stdint.h>

#define _XTAL_FREQ 32000000
#define WS2812_0 0b100
#define WS2812_1 0b110
#define NUM_BYTES_PER_COLOR 4

void SPI_Init(void);
void encodeByte(uint8_t inputByte, uint8_t outArray[4]);
void sendColor_SPI(uint8_t g, uint8_t r, uint8_t b);

#endif
