#include <LiquidCrystal.h>

int bright_in = 0, volume_in = 0, bright_per = 0, volume_per = 0;
char brigth_str[4] = {}, volume_str[4] = {}, output[8] = {};

LiquidCrystal lcd(12, 11, 7, 6, 5, 4);

void read()
{
    if (Serial.available() <= 0) return;
    String line = Serial.readStringUntil('\n');
    snprintf(volume_str, 4, "%3d", line.substring(0, line.indexOf(',')).toInt());
    lcd.setCursor(12, 0);
    lcd.print(volume_str);

    snprintf(brigth_str, 4, "%3d", line.substring(line.indexOf(',') + 1).toInt());
    lcd.setCursor(12, 1);
    lcd.print(brigth_str);
}

void write()
{
    bright_in = analogRead(A0);
    volume_in = analogRead(A1);
    int bright_temp = map(bright_in, 0, 1020, 0, 100);
    int volume_temp = map(volume_in, 0, 1020, 0, 100);

    if (volume_temp == volume_per && bright_temp == bright_per) return;

    volume_per = volume_temp;
    bright_per = bright_temp;

    snprintf(volume_str, 4, "%3d", volume_per);
    snprintf(brigth_str, 4, "%3d", bright_per);
    snprintf(output, 8, "%d,%d", volume_per, bright_per);
    Serial.println(output);
}

void setup()
{
    lcd.begin(16, 2);
    lcd.display();
    pinMode(A0, INPUT);
    pinMode(A1, INPUT);
    Serial.begin(9600);

    lcd.clear();
    lcd.setCursor(1, 0);
    lcd.print("Volumen:");
    lcd.setCursor(1, 1);
    lcd.print("Brillo:");
}

void loop()
{
    read();
    write();   

    // delay(50);
}
