# include "Dynamixel_motor_packet.h"

dynamixel_motor_packet::dynamixel_motor_packet()
{

}

dynamixel_motor_packet::dynamixel_motor_packet(int _ID, int _serial_port, int _encoder_resolution)
{
  ID = _ID;
  serial_port = _serial_port;
  encoder_resolution = _encoder_resolution;
}

void dynamixel_motor_packet::Motor_init()
{
  if (serial_port == 1)
  {
    Motor_serial = &Serial1;
    Serial1.begin(BAUDRATE);
  }
  else if (serial_port == 2) 
  {
    Motor_serial = &Serial2;
    Serial2.begin(BAUDRATE);
  }
  else if (serial_port == 3) 
  {
    Motor_serial = &Serial3;
    Serial3.begin(BAUDRATE);
    Serial3.transmitterEnable(13);
  }
  else if (serial_port == 4) 
  {
    Motor_serial = &Serial4;
    Serial4.begin(BAUDRATE);
  }
  else if (serial_port == 5) 
  {
    Motor_serial = &Serial5;
    Serial5.begin(BAUDRATE);
    Serial5.transmitterEnable(2);
  }
  else 
  {
    Serial.println("!!!!!!!!!!!!!!!! Serial Port Error !!!!!!!!!!!!!!!!");
  }
}

void dynamixel_motor_packet::Motor_angle_control(float _angle)
{
  uint16_t motor_output_position = _angle * (4096.0 / 360.0);
  byte data_1 = motor_output_position & 0xFF;               // Low byte
  byte data_2 = (motor_output_position >> 8) & 0xFF;        // High byte
 
  Send_buffer[0] = 0xFF;                 // header
  Send_buffer[1] = 0xFF;                 // header
  Send_buffer[2] = ID;                   // ID
  Send_buffer[3] = 0x05;                 // length = 5 (3 parameters + 2 bytes instruction/checksum)
  Send_buffer[4] = 0x03;                 // instruction = WRITE
  Send_buffer[5] = 0x1E;                 // parameter 1 = address of goal position low byte
  Send_buffer[6] = data_1;               // goal position low byte (0x0008 => 8)
  Send_buffer[7] = data_2;               // goal position high byte
  Send_buffer[8] = Checksum(Send_buffer, 8);  // calculated checksum
  Serial5.write(Send_buffer, 9);         // send entire packet (9 bytes)
}

void dynamixel_motor_packet::Motor_set_velocity(int _velocity)
{
  byte data_1 = _velocity & 0xFF;               // Low byte
  byte data_2 = (_velocity >> 8) & 0xFF;        // High byte

  Send_buffer[0] = 0xFF;                 // header
  Send_buffer[1] = 0xFF;                 // header
  Send_buffer[2] = ID;                   // ID
  Send_buffer[3] = 0x05;                 // length = 5 (3 parameters + 2 bytes instruction/checksum)
  Send_buffer[4] = 0x03;                 // instruction = WRITE
  Send_buffer[5] = 0x20;                 // parameter 1 = address of goal position low byte
  Send_buffer[6] = data_1;                 // motor velocity low byte
  Send_buffer[7] = data_2;                 // motor velocity high byte            
  Send_buffer[8] = Checksum(Send_buffer, 8);  // calculated checksum
  Serial5.write(Send_buffer, 9);         // send entire packet (9 bytes)
}

void dynamixel_motor_packet::Motor_Read_angle()
{
  Send_buffer[0] = 0xFF;                 // header
  Send_buffer[1] = 0xFF;                 // header
  Send_buffer[2] = ID;                   // ID
  Send_buffer[3] = 0x05;                 // length = 5 (3 parameters + 2 bytes instruction/checksum)
  Send_buffer[4] = 0x02;                 // instruction = READ
  Send_buffer[5] = 0x24;                 // parameter 1 = address of present position request low byte
  Send_buffer[6] = 0x02;                 // present position request low byte (0x0008 => 8)
  Send_buffer[7] = 0x00;                 // present position request high byte
  Send_buffer[8] = Checksum(Send_buffer, 8);  // calculated checksum
  Serial5.write(Send_buffer, 9);         // send entire packet (9 bytes)
}

byte dynamixel_motor_packet::Checksum(byte* arr, int size)
{
  byte checksum = 0x00;

  // Dynamixel checksum sums from ID to last parameter
  for (int i = 2 ; i < size ; i++)
  {
    checksum += arr[i];
  }
  return ~checksum;                 // bitwise NOT of sum
}
