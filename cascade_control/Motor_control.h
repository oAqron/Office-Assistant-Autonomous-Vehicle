# ifndef MOTOR_CONTROL_H
# define MOTOR_CONTROL_H

# include <Arduino.h>
# include <vector>
# include "Dynamixel_motor_packet.h"

# define MOTOR_NUM 2
# define DELAY_TIME 500             // millisecond


class motor_control
{
  private:
    dynamixel_motor_packet motor_arr[MOTOR_NUM];

    byte Serial5_receive_buffer[100] = {0x00};              // define a buffer to store the return packet from serial5
    int Serial5_pkg_num = 0;                                // Counter for serial5 packet
    int Serial5_data_num = 0;                               // Counter for serial5 packet data

    void Serial5_data_decode();
    byte Checksum(byte* arr, int size);

  public:
    motor_control();
    void Controller_position(std::vector<float> _target_position);
    void Controller_velocity(std::vector<int> _target_velocity);
    void Controller_position_request();
    void Serial5_data_receive();
    void Serial5_reset_parameters();

    uint16_t Serial5_decoded_data = 0;                      // Global parameter for storing decoded data
};

# endif