#include <Arduino.h>

// Global parameters
byte buffer[100] = {0x00};                              // define a buffer to store the Dynamixel packet
byte Serial5_receive_buffer[100] = {0x00};              // define a buffer to store the return packet from serial5
int Serial5_pkg_num = 0;                                // Counter for serial5 packet
int Serial5_data_num = 0;                               // Counter for serial5 packet data
uint16_t Serial5_decoded_data = 0;                      // Global parameter for storing decoded data

// Timer
IntervalTimer Timer;

void setup()
{
  // Serial initialize
  Serial.begin(115200);             // USB serial for debug messages
  Serial5.begin(3000000);           // Dynamixel bus serial at 3,000,000 bps
  Serial5.transmitterEnable(2);     // RS485 direction control pin (pin 2)

  //==================================== packet example ==================================== //
  // Dynamixel Motor velocity packet (Write instruction)
  buffer[0] = 0xFF;                 // header
  buffer[1] = 0xFF;                 // header
  buffer[2] = 0x01;                 // ID = 1
  buffer[3] = 0x05;                 // length = 5 (3 parameters + 2 bytes instruction/checksum)
  buffer[4] = 0x03;                 // instruction = WRITE
  buffer[5] = 0x20;                 // parameter 1 = address of goal position low byte
  buffer[6] = 0x0A;                 // motor velocity low byte
  buffer[7] = 0x00;                 // motor velocity high byte            
  buffer[8] = Checksum(buffer, 8);  // calculated checksum
  Serial5.write(buffer, 9);         // send entire packet (9 bytes)

  // Dynamixel Goal Position packet (Write instruction)
  buffer[0] = 0xFF;                 // header
  buffer[1] = 0xFF;                 // header
  buffer[2] = 0x01;                 // ID = 1
  buffer[3] = 0x05;                 // length = 5 (3 parameters + 2 bytes instruction/checksum)
  buffer[4] = 0x03;                 // instruction = WRITE
  buffer[5] = 0x1E;                 // parameter 1 = address of goal position low byte
  buffer[6] = 0x00;                 // goal position low byte (0x0008 => 8)
  buffer[7] = 0x08;                 // goal position high byte
  buffer[8] = Checksum(buffer, 8);  // calculated checksum
  Serial5.write(buffer, 9);         // send entire packet (9 bytes)

  // Dynamixel present position packet (Read instruction)
  buffer[0] = 0xFF;                 // header
  buffer[1] = 0xFF;                 // header
  buffer[2] = 0x01;                 // ID = 1
  buffer[3] = 0x05;                 // length = 5 (3 parameters + 2 bytes instruction/checksum)
  buffer[4] = 0x02;                 // instruction = READ
  buffer[5] = 0x24;                 // parameter 1 = address of present position request low byte
  buffer[6] = 0x02;                 // present position request low byte (0x0008 => 8)
  buffer[7] = 0x00;                 // present position request high byte
  buffer[8] = Checksum(buffer, 8);  // calculated checksum
  Serial5.write(buffer, 9);         // send entire packet (9 bytes)
  //==================================== packet example ==================================== //

  //==================================== Timer type 1 ==================================== //
  // Timer.begin(Timer_callback, 1e4);   // Using timer to operate some commands in specific frequency
  //==================================== Timer type 1 ==================================== //
}

void loop()
{
  //==================================== Timer type 2 ==================================== //
  // static unsigned long last_update_time = 0;
  // const unsigned long update_interval_us = 10000;

  // unsigned long now = micros();
  // if (now - last_update_time >= update_interval_us)
  // {
  //   last_update_time = now;
  //   Timer_callback();  // 等同於原本的 Timer_callback
  // }
  //==================================== Timer type 2 ==================================== //
}

void serialEvent5()
{
  receive_5();
}

void receive_5()
{
  while(Serial5.available() > 0)
  {
    byte Serial5_tmp = Serial5.read();                                              // Read byte
    if (Serial5_pkg_num == 0 && Serial5_tmp == 0xFF)                                // Header
    {
      Serial5_receive_buffer[Serial5_pkg_num ++] = Serial5_tmp;
    }
    else if (Serial5_pkg_num == 1 && Serial5_tmp == 0xFF)                           // Header
    {
      Serial5_receive_buffer[Serial5_pkg_num ++] = Serial5_tmp;
    }
    else if (Serial5_pkg_num == 2)                                                  // ID
    {
      Serial5_receive_buffer[Serial5_pkg_num ++] = Serial5_tmp;
    }
    else if (Serial5_pkg_num == 3)                                                  // Length
    {
      Serial5_receive_buffer[Serial5_pkg_num ++] = Serial5_tmp;
    }
    else if (Serial5_pkg_num == 4)                                                  // Error code
    {
      Serial5_receive_buffer[Serial5_pkg_num ++] = Serial5_tmp;       
    }
    else if (Serial5_pkg_num > 4)                                                   // Parameters(Data)
    {
      Serial5_receive_buffer[Serial5_pkg_num ++] = Serial5_tmp;
      Serial5_data_num ++;

      if (byte(Serial5_data_num + 1) == byte(Serial5_receive_buffer[3]))            // While receiving specific length data(include error code)
      {
        // Read CRC16
        byte checksum_read = Serial5_receive_buffer[Serial5_pkg_num - 1];
        
        // Calculate CRC16
        byte checksum_cal = Checksum(Serial5_receive_buffer, Serial5_pkg_num - 1);

        if (checksum_read == checksum_cal)                                          // Check sum
        {
          // Print received packet
          Serial.println("========================================");
          Serial.print("Receive packet: ");
          for (int i = 0 ; i < Serial5_pkg_num ; i ++)
          {
            Serial.print(Serial5_receive_buffer[i], HEX);
            Serial.print("\t");
          }
          Serial.println();

          // Decode return packet
          Serial5_data_decode();

          // Reset parameters
          reset_serial5_parameters();
        }
        else                                                                        // When check sum is not pass
        {
          // Reset parameters
          Serial.println("!!!!!!!!!!!!!!!! Check sum not pass !!!!!!!!!!!!!!!!");
          reset_serial5_parameters();
        }
      }
    }
  }
}

// Decode receive data
void Serial5_data_decode()
{
  if (Serial5_receive_buffer[4] == 0)
  {
    if (Serial5_receive_buffer[3] == 2)
    {
      Serial5_decoded_data = 9999;
    }
    else if (Serial5_receive_buffer[3] == 3)
    {
      Serial5_decoded_data = Serial5_receive_buffer[5];
    }
    else if (Serial5_receive_buffer[3] == 4)
    {
      Serial5_decoded_data = Serial5_receive_buffer[5] | (Serial5_receive_buffer[6] << 8);
      // Show decoded data
      Serial.println("========================================");
      Serial.print("Decoded data: \t");
      Serial.println(Serial5_decoded_data);
    }
  }
  else
  {
    Serial.println("!!!!!!!!!!!!!!!! Motor error !!!!!!!!!!!!!!!!");
    Serial.print("error code: \t");
    Serial.println(Serial5_receive_buffer[4]);
  }
}

// Reset parameters
void reset_serial5_parameters()
{
  Serial5_pkg_num = 0;
  Serial5_data_num = 0;
}

// Checksum calculation function
byte Checksum(byte* arr, int size)
{
  byte checksum = 0x00;

  // Dynamixel checksum sums from ID to last parameter
  for (int i = 2 ; i < size ; i++)
  {
    checksum += arr[i];
  }
  return ~checksum;                 // bitwise NOT of sum
}

void Timer_callback()
{
  float sin_angle = sinWave();
  uint16_t motor_output_position = sin_angle * (4096.0 / 360.0);
  byte data_1 = motor_output_position & 0xFF;               // Low byte
  byte data_2 = (motor_output_position >> 8) & 0xFF;        // High byte

  // Dynamixel Goal Position packet (Write instruction)
  buffer[0] = 0xFF;                 // header
  buffer[1] = 0xFF;                 // header
  buffer[2] = 0x01;                 // ID = 1
  buffer[3] = 0x05;                 // length = 5 (3 parameters + 2 bytes instruction/checksum)
  buffer[4] = 0x03;                 // instruction = WRITE
  buffer[5] = 0x1E;                 // parameter 1 = address of goal position low byte
  buffer[6] = data_1;               // goal position low byte (0x0008 => 8)
  buffer[7] = data_2;               // goal position high byte
  buffer[8] = Checksum(buffer, 8);  // calculated checksum
  Serial5.write(buffer, 9);         // send entire packet (9 bytes)

  // Dynamixel present position packet (Read instruction)
  buffer[0] = 0xFF;                 // header
  buffer[1] = 0xFF;                 // header
  buffer[2] = 0x01;                 // ID = 1
  buffer[3] = 0x05;                 // length = 5 (3 parameters + 2 bytes instruction/checksum)
  buffer[4] = 0x02;                 // instruction = READ
  buffer[5] = 0x24;                 // parameter 1 = address of present position request low byte
  buffer[6] = 0x02;                 // present position request low byte (0x0008 => 8)
  buffer[7] = 0x00;                 // present position request high byte
  buffer[8] = Checksum(buffer, 8);  // calculated checksum
  Serial5.write(buffer, 9);         // send entire packet (9 bytes)
}

float sinWave()
{
  float t = millis() / 1000.0;
  float Amplitude = 45.0;
  float frequency = 0.1;
  float offset = 45.0;
  float sin_angle = Amplitude * sin(2 * PI * frequency * t) + offset;
  return sin_angle;
}
