// d750-relay: lets the station computer power cycle the TM-D750 through a relay on its DC feed.
//
// Runs on the LattePanda 3 Delta's own Arduino Leonardo (ATmega32U4), which the station computer sees as
// /dev/serial/by-id/usb-Unknown_LattePanda_Leonardo-if00. Written Wednesday, November 11, 2026.
//
// Wiring, fail safe: the radio's +13.8 V runs through the relay's NORMALLY CLOSED contact. With the
// relay at rest the radio is powered, so a dead Leonardo, a reboot of the station computer, or a cut USB cable all
// leave the radio on. The radio draws over 10 A at 50 W, so the contact that carries it must be rated
// 20 A DC or more; a small relay module on RELAY_PIN driving an automotive relay is one way.
//
// Serial commands, one per line, any case, 9600 baud (never open the port at 1200 baud: that puts the
// Leonardo in its bootloader):
//   status        Pass: radio power on   |   Note: radio power off, back on in N s
//   cycle [N]     power off for N seconds (3 to 60, default 10), then on again by itself
//   on            power back on now
//   id            d750-relay version, pin and polarity
// There is no plain "off": the relay can never leave the radio off for more than MAX_OFF_S.

const int RELAY_PIN = 7;               // the relay module's input
const bool RELAY_ACTIVE_LOW = true;    // most cheap relay modules switch on when their input is LOW
const unsigned long MAX_OFF_S = 60;    // the longest the radio is ever left off
const unsigned long MIN_GAP_S = 30;    // a new cycle only this long after the last one ended
const char VERSION[] = "d750-relay 1.0";

bool off = false;
unsigned long offUntil = 0, lastOn = 0;
bool everCycled = false;
String line;

void relayRest() {                     // relay at rest: normally closed contact closed, radio powered
  digitalWrite(RELAY_PIN, RELAY_ACTIVE_LOW ? HIGH : LOW);
}

void relayPull() {                     // relay pulled in: contact open, radio unpowered
  digitalWrite(RELAY_PIN, RELAY_ACTIVE_LOW ? LOW : HIGH);
}

void powerOn(const char *why) {
  relayRest();
  if (off) {
    off = false;
    lastOn = millis();
    Serial.print("OK: radio power on, ");
    Serial.println(why);
  }
}

void setup() {
  relayRest();                         // first thing, before anything can go wrong: radio powered
  pinMode(RELAY_PIN, OUTPUT);
  relayRest();
  Serial.begin(9600);                  // no waiting for the host: the relay must work without the station computer
}

void answer(String cmd) {
  cmd.trim();
  cmd.toLowerCase();
  if (cmd.length() == 0) return;
  if (cmd == "status") {
    if (off) {
      Serial.print("Note: radio power off, back on in ");
      Serial.print((offUntil - millis()) / 1000 + 1);
      Serial.println(" s");
    } else {
      Serial.println("Pass: radio power on");
    }
  } else if (cmd == "id") {
    Serial.print(VERSION);
    Serial.print(", pin ");
    Serial.print(RELAY_PIN);
    Serial.println(RELAY_ACTIVE_LOW ? ", active low" : ", active high");
  } else if (cmd == "on") {
    if (off) powerOn("by command"); else Serial.println("Pass: radio power on");
  } else if (cmd.startsWith("cycle")) {
    long n = cmd.length() > 5 ? cmd.substring(5).toInt() : 10;
    if (n < 3) n = 3;
    if (n > (long)MAX_OFF_S) n = MAX_OFF_S;
    if (off) {
      Serial.println("Fail: already cycling");
    } else if (everCycled && millis() - lastOn < MIN_GAP_S * 1000UL) {
      Serial.print("Fail: the last cycle ended less than ");
      Serial.print(MIN_GAP_S);
      Serial.println(" s ago");
    } else {
      relayPull();
      off = true;
      everCycled = true;
      offUntil = millis() + (unsigned long)n * 1000UL;
      Serial.print("OK: radio power off for ");
      Serial.print(n);
      Serial.println(" s");
    }
  } else {
    Serial.println("Fail: unknown command; try status, cycle 10, on, id");
  }
}

void loop() {
  if (off && (long)(millis() - offUntil) >= 0) powerOn("cycle done");
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      answer(line);
      line = "";
    } else if (line.length() < 40) {
      line += c;
    }
  }
}
