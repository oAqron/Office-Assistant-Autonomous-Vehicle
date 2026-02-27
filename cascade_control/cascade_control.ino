# include <Arduino.h>
# include <vector>
# include "Motor_control.h"

motor_control motor_controller;

std::vector<int> test_velocity = {1000, 500};
std::vector<float> test_position = {270.0, 180.0};

void setup() {
  Serial.begin(115200);
  motor_controller.Controller_velocity(test_velocity);
  motor_controller.Controller_position(test_position);
  delay(5000);
  motor_controller.Controller_position_request();
}

void loop() {
  // put your main code here, to run repeatedly:

}

void serialEvent5()
{
  motor_controller.Serial5_data_receive();
}
