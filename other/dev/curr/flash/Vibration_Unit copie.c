/* 
 * File:   main.c
 * Author: MasonC
 *
 * Created on November 8, 2022, 10:19 PM
 * Modified for 100 duty levels
 */

 #include <stdio.h>
 #include <stdlib.h>
 #include "neopixel_control.h"
 
 
 
 // PIC16F18313 Configuration Bit Settings
 
 // 'C' source line config statements
 
 // CONFIG1
 #pragma config FEXTOSC = OFF    // FEXTOSC External Oscillator mode Selection bits (Oscillator not enabled)
 #pragma config RSTOSC = HFINT32  // Power-up default value for COSC bits (HFINTOSC (1MHz))
 #pragma config CLKOUTEN = OFF   // Clock Out Enable bit (CLKOUT function is disabled; I/O or oscillator function on OSC2)
 #pragma config CSWEN = OFF      // Clock Switch Enable bit (The NOSC and NDIV bits cannot be changed by user software)
 #pragma config FCMEN = OFF      // Fail-Safe Clock Monitor Enable (Fail-Safe Clock Monitor is disabled)
 
 // CONFIG2
 #pragma config MCLRE = ON       // Master Clear Enable bit (MCLR/VPP pin function is MCLR; Weak pull-up enabled )
 #pragma config PWRTE = OFF      // Power-up Timer Enable bit (PWRT disabled)
 #pragma config WDTE = OFF       // Watchdog Timer Enable bits (WDT disabled; SWDTEN is ignored)
 #pragma config LPBOREN = OFF    // Low-power BOR enable bit (ULPBOR disabled)
 #pragma config BOREN = OFF      // Brown-out Reset Enable bits (Brown-out Reset disabled)
 #pragma config BORV = LOW       // Brown-out Reset Voltage selection bit (Brown-out voltage (Vbor) set to 2.45V)
 #pragma config PPS1WAY = OFF    // PPSLOCK bit One-Way Set Enable bit (The PPSLOCK bit can be set and cleared repeatedly (subject to the unlock sequence))
 #pragma config STVREN = ON      // Stack Overflow/Underflow Reset Enable bit (Stack Overflow or Underflow will cause a Reset)
 #pragma config DEBUG = OFF      // Debugger enable bit (Background debugger disabled)
 
 // CONFIG3
 #pragma config WRT = OFF        // User NVM self-write protection bits (Write protection off)
 #pragma config LVP = OFF         // Low Voltage Programming Enable bit (Low voltage programming enabled. MCLR/VPP pin function is MCLR. MCLRE configuration bit is ignored.)
 
 // CONFIG4
 #pragma config CP = OFF         // User NVM Program Memory Code Protection bit (User NVM code protection disabled)
 #pragma config CPD = OFF        // Data NVM Memory Code Protection bit (Data NVM code protection disabled)
 
 // #pragma config statements should precede project file includes.
 // Use project enums instead of #define for ON and OFF.
 #include <xc.h>
 #include <stdint.h>
 #include <stdlib.h>
 #define _XTAL_FREQ  32000000     // Set clock frequency 
 
 uint8_t buffer = 0;//uart recv buffer
 uint8_t parity = 0;//uart recv parity
 uint8_t uart_recv_flag = 0;
 
 uint8_t duty_index = 0; // 0-99 maps to PWM duty cycle 0-99%;
 uint8_t duty_cycle = 0;
 uint8_t freq_index = 3; // 0-7 maps to frequency {123, 145, 170, 200, 235, 275, 322, 384} Hz;
 
 //uint8_t PR_val[] = {127, 107, 91, 78, 66, 56, 48, 40}; // PR2 values for frequencies;
 uint8_t PR_val[] = {85, 72, 60, 52, 44, 37, 32, 27}; // PR2 values for frequencies;
 
 uint8_t ccp_flag = 0;
 uint8_t cwg_flag = 0;
 uint8_t duty_flag = 0;
 // Index into sine table
 uint8_t index = 0;
 uint8_t state = 0; // 0=idle, 1=expecting_duty, 2=expecting_freq
 
 // neopixel color
 uint8_t color_index = 0;
 uint8_t color[] = {0,0,0};
 
 // Protocol state variables
 uint8_t received_duty = 0;
 uint8_t received_freq = 0;
 uint8_t data_byte_count = 0;
 
 void init_ccp_cwg(void) {
     // Set PA0, PA1 Pin as output
     TRISA0 = 1;//first set the flag to disable PA0 and PA1 outputs
     TRISA1 = 1;
     ANSELA = 0; // all digital
     WPUA = 0; // weak pullup
     //RA1PPS = 12; // Output CCP1 to RA1
     RA1PPS = 0b01000; //get cwg1a
     RA0PPS = 0b01001;//get cwg1b
     // Set CCP1CON register to PWM mode
     CCP1CON = 0b10011111;//FMT = 1
     CCP1IE = 1;
     // CCP1IF = 1;
     // Enable Global Interrupts
     GIE = 1;
     
     // Enable Peripheral Interrupts
     PEIE = 1;
     TMR2IE = 1; //enable interrupt on timer2
     // Set PR2 with appropriate PWM period
     
     // Set Timer2 Control Register
     T2CON = 0b00000001; // Timer 2 PS1/4 setting
     PR2 = PR_val[freq_index];
     
     //set cwg
   
     CWG1CON0 = 0b01000100;//half bridge, disable
     CWG1CON1 = 0;//A--non-invert, B--invert, C--non-invert, D--invert
     CWG1DAT = 0b00000011;//set data input to ccp1
     CWG1AS0 = 0b01111000;//disable autoshutdown, all 0 when shutdown occurs
     CWG1DBR = 0b0;
     CWG1DBF = 0b0;
     CWG1CLKCON = 1; //select hfint clk
     CWG1CON0bits.EN = 1;
     __delay_us(100);
 }
 
 void usart_init() {
     TRISA5 = 1; //port 5 as RXinput
     TRISA2 = 1; //port 2 as TXout
     ANSELA = 0;
     RXPPS = 0b00101; //port5 RX
     RA2PPS = 0b10100; //port2 TX
 
     RC1STA = 0b10010000; // 8 bit continuous reception CREN = 1 SPEN = 1
     TX1STA = 0b00100100; // Asynchronous reception High Baud Rate selection BRGH = 1  TXEN = 1; //transmit enable //async mode
     BAUD1CON = 0b00001000; // 16 bit SPBRG   BRG16 = 1
     SP1BRGH = 0;
     SP1BRGL = 68; // 115.2k baud rate
     TX9 = 1; //enable 9bit transmission
     RX9 = 1; //enable 9-bit recv
     RCIE = 1; //receive interrupt enable
     //IDLEN = 1; // Idle inhibits the CPU clk
 
     __delay_us(100); //wait for set up
 
 }
 uint8_t make_addr_byte(uint8_t start, uint8_t addr){
     //make the first, address byte for transmission
     uint8_t addr_byte = 0;
     addr_byte |= (start & 0b1);
     addr_byte |= (addr << 1);
    
     return addr_byte;
 }
 uint8_t getParity(uint8_t n)
 { //return the parity of n. if odd, return 1, even, return 0
     uint8_t parity = 0;
     while (n)
     {
         parity = !parity;
         n = n & (n - 1);
     }
     return (parity & 0b1);
 }
 
 void UART_Write(uint8_t data) {
     while(!TRMT){};
     
     TX9D = (getParity(data) & 0b1);
     TX1REG = data;
     
 }
 
 void UART_processing(){
     if(getParity(buffer) != parity) return; //drop packet 
     if((buffer >> 7) != 0b1){ //addr byte recved
         uint8_t addr = (buffer >> 1); //get addr
         uint8_t start = (buffer & 0b1); //get start/stop
         if(addr != 0){ //not the current address
             state = 0;// if state = 1 but the byte after is not data byte, then the unit should reset, to let commands go through.
             data_byte_count = 0; // Reset data byte counter
             --addr; //decrease addr
             UART_Write(make_addr_byte(start, addr)); //send
             return;
         }
         else{ //the current addr
             if(start == 1) {
                 state = 1; // expecting duty byte
                 data_byte_count = 0;
             } else {
                 state = 0; // stop
                 data_byte_count = 0;
                 TMR2ON = 0;//ccp disable 
                 TRISA0 = 1;
                 TRISA1 = 1;
                 duty_index = 0;
             }
             return;
         }
     
     }
     else { //data byte received
         if(state == 0){ //previous data byte not address to this board
                 while(!TRMT){};
                 TX9D = parity & 0b1;
                 TX1REG = buffer;//transmit directly
                 return;
         }
         else if(state == 1) { // expecting duty byte
             received_duty = buffer & 0x7F; // Strip the data byte marker bit (0x80)
             if(received_duty > 99) received_duty = 99; // Clamp to 0-99
             state = 2; // now expecting frequency byte
             return;
         }
         else if(state == 2) { // expecting frequency byte
             received_freq = buffer & 0b111; // only use lower 3 bits (0-7)
             if(received_freq > 7) received_freq = 7; // Clamp to 0-7
             
             // Now we have both values, apply them
             TRISA1 = 0;
             TRISA0 = 0;
             T2CON = 0b00000101;
             
             freq_index = received_freq;
             duty_index = received_duty;
             duty_cycle = duty_index; // Direct mapping: 0-99
             
             PR2 = PR_val[freq_index]; //load freq
             state = 0; // reset state
             data_byte_count = 0;
             return;
         }
     }
 }
 
 void CCP_processing(){
     // update CWG and CCP statuses based on the current index
     if((index >= 0 && index < duty_cycle) || (index >= 100 && index < (duty_cycle + 100))){
         if (cwg_flag == 0){
             // keep RA0 and RA1 the opposite
             CWG1CON0bits.EN = 0;
             CWG1CON1bits.POLB= 0;
             CWG1CON0bits.EN = 1;
             cwg_flag = 1;
         }
     }
     else{
         if (cwg_flag == 1){
             // keep RA0 and RA1 the same
             CWG1CON0bits.EN = 0;
             CWG1CON1bits.POLB = 1;
             CWG1CON0bits.EN = 1;
             cwg_flag = 0;
         }
     }
     if(index >= 0 && index < duty_cycle){
         if (duty_flag == 0){
             // full duty cycle
             CCPR1H = PR_val[freq_index];
             CCPR1L= 0x00;
             duty_flag = 1;
         }
     }
     else{
         if (duty_flag == 1){
             // near-zero duty cycle
             CCPR1H = 0x00;
             CCPR1L= 64;
             duty_flag = 0;
         }
     }
 }
 
 void getColor(uint8_t duty_index, uint8_t color[3]) {
     // Ensure the duty_index is within the expected range
     if (duty_index > 99) duty_index = 99;
 
     // Map 0-99 to colors using a smooth gradient
     if (duty_index == 0) {
         // Black (Off)
         color[0] = 0; color[1] = 0; color[2] = 0;
     } else if (duty_index <= 16) {
         // Blue to Cyan (0-16)
         uint8_t intensity = (duty_index * 255) / 16;
         color[0] = 0;           // G = 0
         color[1] = 0;           // R = 0  
         color[2] = intensity;   // B = 0 to 255
     } else if (duty_index <= 33) {
         // Cyan to Green (17-33)
         uint8_t progress = duty_index - 17;
         uint8_t fade = (progress * 255) / 16;
         color[0] = fade;        // G = 0 to 255
         color[1] = 0;           // R = 0
         color[2] = 255 - fade;  // B = 255 to 0
     } else if (duty_index <= 50) {
         // Green to Yellow (34-50)
         uint8_t progress = duty_index - 34;
         uint8_t fade = (progress * 255) / 16;
         color[0] = 255;         // G = 255
         color[1] = fade;        // R = 0 to 255
         color[2] = 0;           // B = 0
     } else if (duty_index <= 66) {
         // Yellow to Orange (51-66)
         uint8_t progress = duty_index - 51;
         uint8_t fade = (progress * 255) / 15;
         color[0] = 255 - (fade/2); // G = 255 to 128
         color[1] = 255;            // R = 255
         color[2] = 0;              // B = 0
     } else if (duty_index <= 83) {
         // Orange to Red (67-83)
         uint8_t progress = duty_index - 67;
         uint8_t fade = (progress * 255) / 16;
         color[0] = 128 - (fade/2); // G = 128 to 0
         color[1] = 255;            // R = 255
         color[2] = 0;              // B = 0
     } else {
         // Red to White (84-99)
         uint8_t progress = duty_index - 84;
         uint8_t fade = (progress * 255) / 15;
         color[0] = fade;           // G = 0 to 255
         color[1] = 255;            // R = 255
         color[2] = fade;           // B = 0 to 255
     }
 }
 
 // Timer2 Interrupt Service Routine
 void __interrupt() ISR(void) {
         if (RCIF) {
             RCIF = 0; // Clear The Flag
             parity = RX9D; //read the 9th parity
             buffer = RC1REG; // Read The Received Data Buffer
             UART_processing();
             uart_recv_flag = 1;
         }
         else if(TMR2IF){
             TMR2IF = 0;
             index = index + 1;
             if(index == 200)
                 index = 0;
             ccp_flag = 1;
         }
         else if(CCP1IF){
             CCP1IF = 0; //clear flag
         }
     
 }
 
 int main(int argc, char** argv) {
 
     // Initialize CCP Module
 //    TRISA4 = 0;
 //    WDTCON = 0b100011;
     init_ccp_cwg();
     usart_init();
     SPI_Init();
    
     // Infinite loop
     while(1) {
         if (uart_recv_flag) {
             uart_recv_flag = 0;
             // also check if the color needs to be updated
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