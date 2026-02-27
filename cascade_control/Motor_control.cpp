# include "Motor_control.h"

motor_control::motor_control()
{
  for (int i = 0 ; i < MOTOR_NUM ; i ++)
  {
    motor_arr[i] = dynamixel_motor_packet(i + 1, 5, 4096);
    motor_arr[i].Motor_init();
  }
}

void motor_control::Controller_position(std::vector<float> _target_position)
{
  for (int i = 0 ; i < MOTOR_NUM ; i ++)
  {
    motor_arr[i].Motor_angle_control(_target_position[i]);
    delayMicroseconds(DELAY_TIME);
  }
}

void motor_control::Controller_velocity(std::vector<int> _target_velocity)
{
  for (int i = 0 ; i < MOTOR_NUM ; i ++)
  {
    motor_arr[i].Motor_set_velocity(_target_velocity[i]);
    delayMicroseconds(DELAY_TIME);
  }
}

void motor_control::Controller_position_request()
{
  for (int i = 0 ; i < MOTOR_NUM ; i ++)
  {
    motor_arr[i].Motor_Read_angle();
    delayMicroseconds(DELAY_TIME);
  }
}

void motor_control::Serial5_data_receive()
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
          Serial5_reset_parameters();
        }
        else                                                                        // When check sum is not pass
        {
          // Reset parameters
          Serial.println("!!!!!!!!!!!!!!!! Check sum not pass !!!!!!!!!!!!!!!!");
          Serial5_reset_parameters();
        }
      }
    }
  }
}

// Decode receive data
void motor_control::Serial5_data_decode()
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

void motor_control::Serial5_reset_parameters()
{
  Serial5_pkg_num = 0;
  Serial5_data_num = 0;
}

byte motor_control::Checksum(byte* arr, int size)
{
  byte checksum = 0x00;

  // Dynamixel checksum sums from ID to last parameter
  for (int i = 2 ; i < size ; i++)
  {
    checksum += arr[i];
  }
  return ~checksum;                 // bitwise NOT of sum
}