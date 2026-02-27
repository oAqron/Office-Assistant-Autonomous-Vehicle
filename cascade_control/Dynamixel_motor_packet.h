# ifndef DYNAMIXEL_MOTOR_PACKET_H
# define DYNAMIXEL_MOTOR_PACKET_H

# include <Arduino.h>

# define BAUDRATE 3000000
# define SEND_DELAY 500

class dynamixel_motor_packet
{
  private:
    int ID = 0;
    int serial_port = 0;
    int encoder_resolution = 4096;
    int baudrate = BAUDRATE;
    Stream* Motor_serial = &Serial1;
    byte Send_buffer[100] = {0};
    byte Checksum(byte* arr, int size);

  public:
    dynamixel_motor_packet();
    dynamixel_motor_packet(int _ID, int _serial_port, int _encoder_resolution);
    void Motor_init();                                                                    // Initialize baudrate
    void Motor_angle_control(float _angle);                                               // Position control
    void Motor_set_velocity(int _velocity);                                               // Motor angular speed setting
    void Motor_Read_angle();                                                              // Read motor angle
};

# endif
