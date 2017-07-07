#define CLOCK_PIN                     5                   // clock for switches, PORTD (PD5)
#define SYNC_PIN                      4                   // sync for switches, PORTD (PD4)
#define DATA_OUT_PIN                  7                   // daisy chain output pin, PORTD (PD7)
#define CAMERA_TRIGGER_PIN            3                   // trigger Thorlabs camera, PORTD (PD3)
#define TILTING_PIN                   2                   // trigger for the tilting machine, PORTD (PD2)
#define LED_PIN                       13

#define DIO_LINE_PORT                 PORTB               // all dio lines for HF2 are on PORTB

#define DATA_OUT_HIGH                 {PORTD |= 0x80;}
#define DATA_OUT_LOW                  {PORTD &= 0x7F;}

#define CLOCK_HIGH                    {PORTD |= 0x20;}
#define CLOCK_LOW                     {PORTD &= 0xDF;}
#define CLOCK_TOGGLE                  {((PORTD>>CLOCK_PIN)&1)?(CLOCK_LOW):(CLOCK_HIGH);}
#define CLOCK_TOGGLE_WITH_DELAY(t)    {delayMicroseconds(t);CLOCK_TOGGLE;}
#define CLOCK_HIGH_WITH_DELAY(t)      {CLOCK_HIGH;delayMicroseconds(t);}
#define CLOCK_LOW_WITH_DELAY(t)       {CLOCK_LOW;delayMicroseconds(t);}

#define SYNC_HIGH                     {PORTD |= 0x10;}
#define SYNC_LOW                      {PORTD &= 0xEF;}

#define CAMERA_TRIG_HIGH              {PORTD |= 0x08;}
#define CAMERA_TRIG_LOW               {PORTD &= 0xF7;}
#define IS_CAMERA_TRIGGER_HIGH        ((PORTD>>CAMERA_TRIGGER_PIN)&1)

#define TILTING_HIGH                  {PORTD |= 0x04;}
#define TILTING_LOW                   {PORTD &= 0xFB;}
#define TILTING_TRIGGER_PULSE         {TILTING_HIGH;TILTING_LOW;}

#define LED_ON                        {PORTB |= 0x20;}
#define LED_OFF                       {PORTB &= 0xDF;}
#define LED_TOGGLE                    {((PORTB>>5)&1)?(LED_OFF):(LED_ON);}

#define DEBUG_PRINT(msg)              {if(debugMode){Serial.println(msg);}}

#define SIZE_OF_ARRAY(arr)            (sizeof(arr)/sizeof(arr[0]))

#define MAX_DATA_LENGTH               512     // receive max 512 byte of data, excluding command string and number
#define MAX_OUTPUT_PINS               16
#define MAX_CHAMBERS                  15      // change if you have more

#define DIO_LINE_BYTES                1
#define SWITCH_BYTES                  2     // put your number of switches here, in case you want to change it
#define INTERVAL_BYTES                4
#define CHAMBER_BYTE_STREAM_LEN       (DIO_LINE_BYTES + SWITCH_BYTES + INTERVAL_BYTES)
#define MAX_NUM_SWITCHES              64


/* --- SWITCHING SCHEMES --- */
struct SwitchingScheme {
  uint8_t  activeSwitches[SWITCH_BYTES] = {0};     // store active switches as bytes from 0 to 8*num_ICs ... with current PCB (Ketki v4.0) 0..63 switches
  uint8_t  hf2DioByte;                             // store 5 bits for DIO lines to HF2
  uint32_t chamberInterval;                        // store 4 bytes of residence time in us for the electrode pair setup, max. 1.19 h, 0 means switch as fast as possible; in case only one electrode pair is selected this time is ignored
};

/* --- SERIAL INPUT PROCESSING --- */
int8_t     bitIdx   = 0;
int8_t     swIdx    = 0;
int8_t     actSwIdx = 0;
uint16_t   byteIdx  = 0;
uint16_t   dataIdx  = 0;
char       data[MAX_DATA_LENGTH] = {'\0'};              // contains all incoming streams, gets overridden evertime a new command is incoming

const char     header[]    = "START ";                  // to recognize a proper start of the command
const char     footer[]    = "END\r";                    // to recognize a proper ending of the command
const char     delimiter[] = " ";                      // to cut the command into its individual parts
const uint8_t  headerLen   = strlen(header);
const uint8_t  footerLen   = strlen(footer);
      int16_t  headerPos   = 0;
      int16_t  footerPos   = 0;
      uint16_t checksumPos = 0;

bool headerFound = false;
bool footerFound = false;

char *checksumString = NULL;           // complete input stream
char *commandString  = NULL;
char *valueString    = NULL;

uint8_t  value          = 0;           // converted input value, max is 255
uint16_t remoteChecksum = 0;           // checksum value of incoming stream
uint16_t localChecksum  = 0;           // checksum value of received bytes (calculated locally)

bool commandComplete  = false;         // whether the string is complete
bool valueComplete    = false;         // whether the value is complete
bool checksumComplete = false;         // whether the value is complete
bool lockCommand      = false;         // to lock certain command execution
bool debugMode        = false;         // enable/disable printouts

/* --- OUTPUT SPEED --- */
uint8_t daisyPeriodTimeHalf = 1;      // This results in a 500 kHz clock (2 us period time)

/* --- PIN STUFF --- */
uint8_t dioOutputsToHF2[] = {8, 9, 10, 11, 12};   //, 13, 14, 15, 16, 17, 18, 19, 20};  // output pins for clock, sync, din, tilt, chamberIndex1, chamberIndex2, ..., chamberIndexN
//int8_t  resetIndex = -1;                          // -1 = no reset pin, otherwise indicates the reset pin that is always pulled up

/* --- THORLABS CAMERA STUFF --- */
uint8_t  cameraFrameRate = 20;        // frame rate in ms for the thorlabs camera
uint8_t  cameraTrigHigh = 100;        // high time of trigger pulse in us
bool     triggerCamera = false;       // should camera be triggered
uint32_t startTimerCamera;
uint32_t stopTimerCamera;
uint32_t cameraTimeFrame = (uint32_t)(1e6/cameraFrameRate);

/* --- DAISYCHAIN AUTO-LOOP --- */
struct   SwitchingScheme *userSwitchingScheme = NULL;       // allocate array depending on how many electrode pairs should be selected
uint8_t  numSwitchingSchemes = 0;
uint16_t daisyFrameRate      = 2000;                        // frame rate in us for the daisychaining
uint32_t startTimerDaisy;
uint32_t stopTimerDaisy;
uint32_t daisyTimeFrame      = (uint32_t)(1e6/daisyFrameRate);
uint8_t  chamberIdx          = 0;

/* --- TILTER STUFF --- */
uint8_t tilterTrigHigh = 100;        // high time of trigger pulse in us
bool tiltPlatform = false;

bool startMeas = false;

/* --- BENCHMARKING --- */
//uint32_t startTime = 0;
//uint32_t endTime = 0;



// the setup function runs once when you press reset or power the board
void setup() {
  // initialize serial
  // NOTE: make sure it's the same speed given in Python code!
  Serial.begin(115200);
  Serial.setTimeout(10);
  
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }

  // might be used without the shield...
//  SPI.begin(); //initialize the SPI protocol

  // define output pins
  pinMode(LED_PIN, OUTPUT);
  pinMode(SYNC_PIN, OUTPUT);
  pinMode(CLOCK_PIN, OUTPUT);
  pinMode(TILTING_PIN, OUTPUT);
  pinMode(DATA_OUT_PIN, OUTPUT);
  pinMode(CAMERA_TRIGGER_PIN, OUTPUT);
  
  for (unsigned short pinIdx = 0; pinIdx < SIZE_OF_ARRAY(dioOutputsToHF2); ++pinIdx) {
    pinMode(dioOutputsToHF2[pinIdx], OUTPUT);
  }
  
  // indicate user correct start
  startBlinkingSequence();
}

void loop() {

  if (startMeas) {
    
    // trigger ThorLabs camera with certain frame rate
    if (triggerCamera && !IS_CAMERA_TRIGGER_HIGH && ( (stopTimerCamera = micros()) - startTimerCamera ) >= cameraTimeFrame) {
      CAMERA_TRIG_HIGH;
      // store time here to get the correct frame rate
      startTimerCamera = stopTimerCamera;
    }
    else if (triggerCamera && IS_CAMERA_TRIGGER_HIGH && ( (stopTimerCamera = micros()) - startTimerCamera ) >= cameraTrigHigh) {
      CAMERA_TRIG_LOW;
    }

    // only select next electrode pair if available and if more than one pair is given
    if (userSwitchingScheme != NULL && numSwitchingSchemes > 1) {
      if ( ((stopTimerDaisy = micros()) - startTimerDaisy ) >= userSwitchingScheme[chamberIdx].chamberInterval) {

        // get next chamber
        ++chamberIdx;

        // reset to zero, if array is smaller
        if (chamberIdx == numSwitchingSchemes) {
          chamberIdx = 0;
        }
        
        writeDaisyChain();
        updateHf2DioLines(userSwitchingScheme[chamberIdx].hf2DioByte);
        startTimerDaisy = stopTimerDaisy;
      }
    }
  }
}

bool FindKeyword(const char *const data, const char *const keyword, const uint16_t dataLen, int16_t *const keywordIdx) {
  // function that tries to find a keyword in a data stream with the maximum length of 32 kB
  
  bool keywordFound = false;
  uint16_t byteIdx  = 0;
  uint16_t keyIdx   = 0;
  uint8_t  keyLen   = strlen(keyword);

  while (!keywordFound && byteIdx < dataLen) {

    // check if character is the same as in keyword
    if (data[byteIdx] == keyword[keyIdx]) {
      ++keyIdx;
      if (keyIdx == keyLen) {
        keywordFound = true;

        if (keywordIdx != NULL) {
          *keywordIdx = byteIdx-keyLen+1;
        }
      }
    }
    // if not reset the index in case we aready had some letters
    else {
      keyIdx = 0;
    }
    
    ++byteIdx;
  }

  // just update keyword index in case nothing was found
  if (!keywordFound && keywordIdx != NULL) {
    *keywordIdx = -1;
  }  

  return keywordFound;
}



void serialEvent() {

  value       = 0;
  dataIdx     = 0;
  headerFound = false;
  footerFound = false;

  remoteChecksum = 0;
  localChecksum  = 0;

  commandComplete = false;
  
  commandString = NULL;
  valueString   = NULL;
  
  // read data from serial port and check for header and footer  
  while (Serial.available() && (!headerFound || !footerFound)) {

    // get new data from serial stream
    dataIdx = Serial.readBytes(&data[dataIdx], MAX_DATA_LENGTH);

    // check for header and footer
    headerFound = FindKeyword(data, header, dataIdx, &headerPos);
    footerFound = FindKeyword(data, footer, dataIdx, &footerPos);
  }

  // here we know both header and footer is in the stream
  if (headerFound && footerFound) {
    
    // clac checksum pos from found header and its length
    // NOTE: header already contains a space, so NO +1 necessary
    checksumPos = headerPos + headerLen;
    
    // let's check the checksum in the next step
    checksumString = strtok( &data[checksumPos], delimiter );

    // first, caluclate local checksum before proceeding
    // calculate checksum - summing up the ASCII values
    // should not work if command is missing - so we can use it to 
    // NOTE: -1 in the loop cause we don't want to count the last space character
    for (byteIdx = checksumPos + strlen(checksumString); byteIdx < footerPos-1; ++byteIdx) {
      localChecksum += (uint8_t)data[byteIdx];
    }

    if (sscanf(checksumString, "%x", &remoteChecksum)) {
      if (localChecksum == remoteChecksum) {
        
        // get command
        commandString = strtok( NULL, delimiter );
        commandComplete = true;
      }
      else {
        Serial.println("ERROR: Received invalid stream, checksums are not identical!");
      }
    }
    else {
      Serial.println("ERROR: Received invalid stream, could not grasp checksum!");
    }
  }
  else {
    Serial.println("ERROR: Received invalid stream, could not find header and/or footer!");
  }
    
      // valid stream so we can check for the command
      if (commandComplete) {
        
//        Serial.println("Received command: " + String(commandString));
        
//        for (int blinkCnt = 0; blinkCnt < 5; ++blinkCnt) {
//          blinkingScheme();
//        }

// -----------------------------------------------------------------------------
      // check for valid command
      if (!strcmp(commandString, "camera")) {

        // cut value from stream
        valueString = strtok( NULL, delimiter );

        if (sscanf(valueString, "%d", &value)) {
          if (value) {
            triggerCamera = true;
          }
          else {
            triggerCamera = false;
          }
        }
        else {
          Serial.println("ERROR: Number expected after command.");
        }
      }
// -----------------------------------------------------------------------------
      else if (!strcmp(commandString, "debug")) {

        // cut value from stream
        valueString = strtok( NULL, delimiter );

        if (sscanf(valueString, "%d", &value)) {
          if (value) {
            debugMode = true;
            Serial.println("Debug mode ON");
          }
          else {
            Serial.println("Debug mode OFF");
            debugMode = false;
          }
        }
        else {
          Serial.println("ERROR: Number expected after command.");
        }
      }
// -----------------------------------------------------------------------------
      else if (!strcmp(commandString, "getversion")) {
        Serial.println("Arduino Uno, ArduinoHandler V0.5");
      }
// -----------------------------------------------------------------------------
      else if (!strcmp(commandString, "help")) {
        // print all available commands
        Serial.println("List of all available commands:\n camera x\n debug x\n getversion\n help\n setelectrodes n 0x00\n setdio x\n setframerate x\n start\n stop\n test\n tilt\n tilter x\n");
      }
// -----------------------------------------------------------------------------
      else if (!strcmp(commandString, "setelectrodes")) {
        /* Define the chambers/electrodes to be selected during one switching scheme started by the command \'start\'.
         * E.g. \'setelectrodes 2 AB10125CD10125\r' will specify two chambers to be stored and can then be selected
         * The last part of the command is interpreted as bytes accordingly:
         *  - 2 bytes active switches
         *  - 1 byte for HF2 DIO line coding
         *  - 4 bytes waiting time in us after the chamber was selected (max. 1.19 h).
         * This scheme of 7 bytes is repeated for each chamber in the list (max. 390 bytes for 15 chambers with two pairs of electrodes).
         * The command 'start' start the selecting scheme and the command 'stop' stops it. 
         * 
         * NOTE: Size of the data capturing array is limited to 512 bytes.
         * NOTE: The 390 bytes are dynamically reserved, which means they should be still available after compiling!!!
        */
        
        
        // calc incrementers and offsets for easy counting
        uint8_t dioOffset      = SWITCH_BYTES;
        uint8_t intervalOffset = DIO_LINE_BYTES + SWITCH_BYTES;
    
        uint16_t inDioIdx;
        uint16_t inByteIdx;
        uint16_t inResIdx;
    
        uint32_t valBuf;

        // cut value from stream
        valueString = strtok( NULL, delimiter );

        if (sscanf(valueString, "%d", &value)) {
          if ( value > 0 && value < ( MAX_DATA_LENGTH / CHAMBER_BYTE_STREAM_LEN ) ) {
    
            // stop timer ... otherwise data structure might be messed up
            // just enable when you encounter problems
            // does not allow you to switch electrode pairs while timer is enabled
            // could be fixed by another variable that stores the initial value and rewrites it at the end of this function
            //startMeas = false;
            
            // check if old data is available, delete it first
            if (userSwitchingScheme != NULL) {
              delete [] userSwitchingScheme;
              
              userSwitchingScheme = NULL;
              chamberIdx          = 0;
              numSwitchingSchemes = 0;
            }
            
            // allocate array with given size for storing bytes accordingly
            userSwitchingScheme = new struct SwitchingScheme[value];
            
            // only proceed if sucessfully allocated
            if (userSwitchingScheme != NULL) {
            
              // update number of electrode pairs, if successful
              numSwitchingSchemes = value;

              // calculate byte stream offset, so where in the whole data stream start the byte stream
              // NOTE: since valueString points to the beginning of the string we need to add the lenght and +1 cause there is a space character
              uint8_t byteStreamOffset = valueString - data + strlen(valueString) + 1;
            
              // store bytes for each chamber setup accordingly
              for (chamberIdx = 0; chamberIdx < numSwitchingSchemes; ++chamberIdx) {
    
                inByteIdx = byteStreamOffset + chamberIdx * CHAMBER_BYTE_STREAM_LEN;
                inDioIdx  = byteStreamOffset + chamberIdx * CHAMBER_BYTE_STREAM_LEN + dioOffset;
                inResIdx  = byteStreamOffset + chamberIdx * CHAMBER_BYTE_STREAM_LEN + intervalOffset;
                
                // first bytes for the switches
                for (byteIdx = 0; byteIdx < SWITCH_BYTES; ++byteIdx) {
                  userSwitchingScheme[chamberIdx].activeSwitches[byteIdx] = (uint8_t)(data[inByteIdx+byteIdx]);   // max 255 switches possible
                }
                
                // DIO lines are always stored after the switch bytes
                userSwitchingScheme[chamberIdx].hf2DioByte = data[inDioIdx];
    
                //Serial.println(data[inDioIdx]);
    
                // make sure nothing strange is in the memory
                userSwitchingScheme[chamberIdx].chamberInterval = 0;
                
                // multiplying with pow is too imprecise
                for (byteIdx = 0; byteIdx < INTERVAL_BYTES; ++byteIdx) {
                  valBuf = data[inResIdx+byteIdx];
                  
                  for (uint8_t shiftIdx = 0; shiftIdx < INTERVAL_BYTES-byteIdx-1; ++shiftIdx) {
                    valBuf = (valBuf << 8);
                  }
                  userSwitchingScheme[chamberIdx].chamberInterval += valBuf;
                }
              }
            
            // select the first chamber right away
            chamberIdx = 0;
            writeDaisyChain();
            updateHf2DioLines(userSwitchingScheme[chamberIdx].hf2DioByte);
            }
            else {
            Serial.println("ERROR: Could not allocate memory for storing switching scheme!");
            }
          }
          else {
            Serial.println("ERROR: Given number of bytes is invalid.");
          }
        }
        else {
          Serial.println("ERROR: Number expected after command.");
        }
      }
// -----------------------------------------------------------------------------
      else if (!strcmp(commandString, "setdio")) {
        // cut value from stream
        valueString = strtok( NULL, delimiter );

        if (sscanf(valueString, "%d", &value)) {
        // sets dio line pins to HF2
          updateHf2DioLines(value);
        }
      }
// -----------------------------------------------------------------------------
      else if (!strcmp(commandString, "setframerate")) {
        // 'setframerate 20' triggers ThorLabs DCC1240C camera 20 times per second
        
        // cut value from stream
        valueString = strtok( NULL, delimiter );

        if (sscanf(valueString, "%d", &value)) {
          if (value) {
            cameraFrameRate = value;
            cameraTimeFrame = 1e6/cameraFrameRate;    // how many microseconds
            
            Serial.println("Camera frame rate " + String(cameraFrameRate));
          }
          else {
            Serial.println("ERROR: Given number of bytes is invalid.");
          }
        }
        else {
          Serial.println("ERROR: Number expected after command.");
        }
      }
// -----------------------------------------------------------------------------
      else if (!strcmp(commandString, "start")) {
        // Start switching chambers (with camera triggering and/or tilting, depending on the setup).
    
        startMeas = true;
        
        // select the first chamber
        if (chamberIdx != 0) {
          chamberIdx = 0;
          writeDaisyChain();
          updateHf2DioLines(userSwitchingScheme[chamberIdx].hf2DioByte);
        }
        
        // start timers...
        startTimerCamera = micros();
        startTimerDaisy  = startTimerCamera;
      }
// -----------------------------------------------------------------------------
      else if (!strcmp(commandString, "stop")) {
        // Stop switching chambers (including camera and tilter triggering).
        startMeas = false;
      }
// -----------------------------------------------------------------------------
      else if (!strcmp(commandString, "test")) {
        for (int blinkCnt = 0; blinkCnt < 5; ++blinkCnt) {
          blinkingScheme();
        }
        // throw user info
        Serial.println("INFO: Test was executed.");
      }
// -----------------------------------------------------------------------------
      else if (!strcmp(commandString, "tilt")) {
        // execute a single trigger pulse to tilt platform
        if (tiltPlatform) {
          TILTING_TRIGGER_PULSE;
        }
      }
// -----------------------------------------------------------------------------
      else if (!strcmp(commandString, "tilter")) {
        /* Specify if a tilter is connected.
        * Call \'tilter 1\' to indicate a tilter is connected and needs to be triggered.
        * Call \'tilter 0\' to virtually unplug the tilter (no more trigger pulses will be generated).
        */
        
        // cut value from stream
        valueString = strtok( NULL, delimiter );

        if (sscanf(valueString, "%d", &value)) {
          if (value) {
            tiltPlatform = true;
          }
          else {
            tiltPlatform = false;
          }
        }
        else {
          Serial.println("ERROR: Number expected after command.");
        }
      }
// -----------------------------------------------------------------------------
  }
}

void writeDaisyChain() {
  // stream received bytes from serial port to data output to change switches
  
  // everything done, release lock
//  bool oldLockState = lockCommand;
//  if (!lockCommand) {
//    lockCommand = true;
//  }

  uint8_t del = 5;
  // enable writing to switches
  // no changes on switches during toogling (only acquired with SYNC HIGH)
  SYNC_LOW;
  
  // write payload
  // changed order of writing, cause first byte which goes out will retain in the last switch
  // don't use for-loop it's too slow...
  
  swIdx = MAX_NUM_SWITCHES;
  actSwIdx = userSwitchingScheme[chamberIdx].activeSwitches[1];     // change number here in case you want to add more switches
  
  // write zeros till switch
  while (--swIdx > actSwIdx) {
    CLOCK_HIGH;
//    delayMicroseconds(del);
    CLOCK_LOW;
//    delayMicroseconds(del);
  }
  
  // write one for switch
  // data is captured on falling edge of clock
  CLOCK_HIGH;
//    delayMicroseconds(del);
  DATA_OUT_HIGH;
//    delayMicroseconds(del);
  CLOCK_LOW;
//    delayMicroseconds(del);
  DATA_OUT_LOW;
//    delayMicroseconds(del);
    
  actSwIdx = userSwitchingScheme[chamberIdx].activeSwitches[0];     // also change here cause it's decrementing...
  // write zeros till switch
  while (--swIdx > actSwIdx) {
    CLOCK_HIGH;
//    delayMicroseconds(del);
    CLOCK_LOW;
//    delayMicroseconds(del);
  }
  
  // write one for switch
  // data is captured on falling edge of clock
  CLOCK_HIGH;
//    delayMicroseconds(del);
  DATA_OUT_HIGH;
//    delayMicroseconds(del);
  CLOCK_LOW;
//    delayMicroseconds(del);
  DATA_OUT_LOW;
//    delayMicroseconds(del);

  ////////////////////////////////////////////////////
  //          --- INSERT BLOCK HERE ---             //
  //   IN CASE YOU WANT TO EXTEND ACTIVE SWITCHES   //
  ////////////////////////////////////////////////////
  
  // write zeros till last switch index...no more active ones after that
  while (--swIdx > -1) {
    CLOCK_HIGH;
//    delayMicroseconds(del);
    CLOCK_LOW;
//    delayMicroseconds(del);
  }
  
  // tell all switches to read register content
  SYNC_HIGH;

//  lockCommand = oldLockState;
}

// set dio lines of HF2 according to chamber number as binary
void updateHf2DioLines(uint8_t chamber) {
  
//  Serial.println("chamber: " + String(chamber));
  
  DIO_LINE_PORT = chamber & 0x1F;   // mask, only five bits are used
}

// send blink sequence to indicate that correct firmware is running
void startBlinkingSequence()
{
  LED_ON;
  delay(500);
  LED_OFF;
  delay(500);
  LED_ON;
  delay(100);
  LED_OFF;
  delay(100);
  LED_ON;
  delay(500);
  LED_OFF;
}

void blinkingScheme() {
  LED_ON;
  delay(300);
  LED_OFF;
  delay(300);
}

// might be used without the shield
/*
//SPI communication to the switches
void writeSPI(int slavePin, byte command){ 
      SPI.beginTransaction(SPISettings(FREQ, MSBFIRST, SPI_MODE1));
      digitalWrite(slavePin, LOW); //set the sync low
      SPI.transfer(command); //convert the int to a byte
      digitalWrite(slavePin, HIGH);
      SPI.endTransaction();
      delay(1);
}*/

