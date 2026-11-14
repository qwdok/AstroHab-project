// AstroHab - كود الأردوينو المعتمد (NodeMCU / ESP8266)
// البروتوكول مع كود بايثون عبر السيريال:
//   الأردوينو يرسل:  exercise_confirmed   عند ضغط زر التمرين
//   الأردوينو يستقبل: BUZZER_ON  و  BUZZER_OFF
//
// نبضة الحياة (fail-safe): بايثون يعيد إرسال الحالة المطلوبة كل ثانية.
// إذا كان الجرس يعمل وانقطعت الأوامر أكثر من COMMAND_TIMEOUT_MS (توقف البرنامج أو انسحب الكابل)
// يُسكت الأردوينو الجرس بنفسه بدل أن يرن بلا نهاية.

// تعيين الدبابيس
const int buttonPin = D1;
const int buzzerPin = D6;

// نوع الجرس: 0 = نشط (Active، يكفيه جهد HIGH)، 1 = سلبي (Passive، يحتاج نغمة tone)
#define PASSIVE_BUZZER 0
const unsigned int TONE_HZ = 2000;

// متغيرات الزر ومنع التكرار (Debounce)
bool lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

// متغيرات الإنذار المتقطع (بدون تعليق الكود)
bool buzzerActive = false;
bool buzzerState = false;
unsigned long previousMillis = 0;
const unsigned long interval = 200;  // سرعة تقطيع الإنذار (كل 200 ميلي ثانية)

// مهلة انقطاع الأوامر قبل الإسكات التلقائي
unsigned long lastBuzzerCommand = 0;
const unsigned long COMMAND_TIMEOUT_MS = 5000;

// استقبال الأوامر بدون حجز البرنامج (بديل readStringUntil الذي ينتظر حتى ثانية)
char cmdBuf[24];
uint8_t cmdLen = 0;

void driveBuzzer(bool on) {
#if PASSIVE_BUZZER
  if (on) {
    tone(buzzerPin, TONE_HZ);
  } else {
    noTone(buzzerPin);
  }
#else
  digitalWrite(buzzerPin, on ? HIGH : LOW);
#endif
  buzzerState = on;
}

void stopBuzzer() {
  buzzerActive = false;
  driveBuzzer(false);  // إيقاف تام فوراً
}

void handleCommand(const char *cmd) {
  if (strcmp(cmd, "BUZZER_ON") == 0) {
    lastBuzzerCommand = millis();  // كل BUZZER_ON يجدد مهلة نبضة الحياة
    if (!buzzerActive) {
      buzzerActive = true;  // بدء الإنذار المتقطع فوراً
      previousMillis = millis();
      driveBuzzer(true);
    }
  } else if (strcmp(cmd, "BUZZER_OFF") == 0) {
    stopBuzzer();
  }
}

void readSerialCommands() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (cmdLen > 0) {
        cmdBuf[cmdLen] = '\0';
        handleCommand(cmdBuf);
        cmdLen = 0;
      }
    } else if (cmdLen < sizeof(cmdBuf) - 1) {
      cmdBuf[cmdLen++] = c;
    } else {
      cmdLen = 0;  // سطر أطول من المتوقع: نتجاهله
    }
  }
}

void setup() {
  // معدل النقل متوافق مع كود بايثون
  Serial.begin(115200);

  pinMode(buttonPin, INPUT_PULLUP);
  pinMode(buzzerPin, OUTPUT);
  driveBuzzer(false);  // إطفاء جرس الإنذار في البداية
}

void loop() {
  // 1. قراءة حالة الزر المادي
  int reading = digitalRead(buttonPin);

  // التحقق من ضغطة الزر واستقرار الإشارة
  if (reading == LOW && lastButtonState == HIGH) {
    if ((millis() - lastDebounceTime) > debounceDelay) {
      // إرسال الإشارة فوراً إلى كود بايثون عبر الكابل
      Serial.println("exercise_confirmed");
      lastDebounceTime = millis();
    }
  }
  lastButtonState = reading;

  // 2. استقبال أوامر التحكم بجرس الإنذار من كود بايثون
  readSerialCommands();

  // 3. الإسكات التلقائي عند انقطاع نبضة الحياة
  if (buzzerActive && (millis() - lastBuzzerCommand) > COMMAND_TIMEOUT_MS) {
    stopBuzzer();
  }

  // 4. تشغيل صوت الإنذار بشكل متقطع حتى يتم إيقافه بالأمر
  if (buzzerActive) {
    unsigned long currentMillis = millis();
    if (currentMillis - previousMillis >= interval) {
      previousMillis = currentMillis;
      driveBuzzer(!buzzerState);  // تبديل الحالة لصنع صفارة متقطعة
    }
  }

  delay(5);  // تأخير بسيط لضمان استقرار العمليات
}
