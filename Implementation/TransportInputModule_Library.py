from pyModbusTCP.client import ModbusClient
from pyModbusTCP.utils import get_bits_from_int
from pyModbusTCP.utils import set_bit
from pyModbusTCP.utils import reset_bit
from pyModbusTCP.utils import test_bit
from time import sleep

from multiprocessing import BoundedSemaphore



class TransportInputModule_Library:
    #Konstanten
    DIGITAL_INPUT_STARTING_ADDRESS = 8001
    DIGITAL_OUTPUT_STARTING_ADDRESS = 8018

    INDEX_CONVEYORS = ['A', 'B', 'C', 'D', 'H', 'I', 'J', 'L', 'M', 'P', 'Q', 'R', 'U', 'V']
    INDEX_SWITCHES = ['E', 'F', 'G', 'K', 'N', 'O', 'S', 'T', 'W']
    #maps index of the conveyors and switches to the Digital I/Os which they are connected to
    INDEX ={
        #Conveyor Index: Outputs -> [>>Move forwards<<, >>Move backward<<], Inputs -> [>>Piece at begin of conveyor<<, >>Piece at end of conveyor<<]
        'A' : [ 0,  1],
        'B' : [ 2,  3, 64, 65], #Two additional sensor bits on conveyors B and R (see documentation)
        'C' : [ 4,  5],
        'D' : [ 6,  7],
        'H' : [20, 21],
        'I' : [22, 23],
        'J' : [24, 25],
        'L' : [30, 31],
        'M' : [32, 33],
        'P' : [42, 43],
        'Q' : [44, 45],
        'R' : [46, 47, 66, 67],
        'U' : [56, 57],
        'V' : [58, 59],

         #Switch Index: Outputs -> [>>Homing<<, >>Position 1<<, >>Position 2<<, >>Position 3<<], Inputs -> [>>Position reached<<, >>In Movement<<, >>Piece in Switch<<, >>Homing Position Sensor<<]
        'E' : [ 8,  9, 10, 11],
        'F' : [12, 13, 14, 15],
        'G' : [16, 17, 18, 19],
        'K' : [26, 27, 28, 29],
        'N' : [34, 35, 36, 37],
        'O' : [38, 39, 40, 41],
        'S' : [48, 49, 50, 51],
        'T' : [52, 53, 54, 55],
        'W' : [60, 61, 62, 63]
    }


    def __init__(self,ip_addr, read_write_sem = BoundedSemaphore(value=1)):
       #"""
        #constructor of the TransportInputModule.

        #:param ip_addr IP address of the Modbus note, which is responsible for the module (String)
        #:param read_write_sem semaphore which can be passed, if reading/writing of I/Os by two modules at the same time has to be locked
        #"""
        try:
             #Establishes a connection through Modbus to ip_addr
            self.client = ModbusClient(host=ip_addr, auto_open=True, auto_close=True)
        except ValueError:
            print("Error with host param")

        #semaphore to allow only one module to access the I/Os
        self.sem = BoundedSemaphore(value=1)

        self.read_write_sem = read_write_sem

        #Conveyor Speed: 0 = 0V/0% (default) | 30000 = 10V/100%
        self.conveyor_speed = {
            'A' : 0,
            'B' : 0,
            'C' : 0, 
            'D' : 0, 
            'H' : 0, 
            'I' : 0, 
            'J' : 0, 
            'L' : 0, 
            'M' : 0, 
            'P' : 0, 
            'Q' : 0, 
            'R' : 0, 
            'U' : 0, 
            'V' : 0, 
        }

    def get_output_register(self, offset = 0, amount = 1):
        #"""
        #Returns output registers of the Modbus node.

        #:param offset Offset to the DIGITAL_OUTPUT_STARTING_ADDRESS
        #:param amount Amount of registers to read
        #:returns List of read registers (or nothing in case of failure)
        #:rtype list of int or none
        #"""
        with self.read_write_sem:
            result = None
            while result == None:
                result = self.client.read_holding_registers(reg_addr=self.DIGITAL_OUTPUT_STARTING_ADDRESS + offset,reg_nb = amount)
            return result

    def get_input_register(self, offset = 0, amount = 1):
        #"""
        #Returns input registers of the Modbus node.

        #:param offset Offset to the DIGITAL_INPUT_STARTING_ADDRESS
        #:param amount  Amount of registers to read
        #:returns List of read registers (or nothing in case of failure)
        #:rtype list of int or none
        #"""
        with self.read_write_sem:
            result = None
            while result == None:
                result = self.client.read_holding_registers(reg_addr=self.DIGITAL_INPUT_STARTING_ADDRESS + offset,reg_nb = amount)
            return result

    def set_output_register(self, register, offset = 0):
        #"""
        #Overwrites output register of the Modbus node.

        #:param register List of int, which are supposed to be written to the register
        #:param offset Offset to the DIGITAL_OUTPUT_STARTING_ADDRESS
        #"""
        with self.read_write_sem:
            result = None
            while result == None:
                result = self.client.write_multiple_registers(self.DIGITAL_OUTPUT_STARTING_ADDRESS + offset, register)

    def get_offset(self, bit_nr):
        #"""
        #Calculates the offset for get_input_register()/get_output_register()/set_output_register() depending on the passed bit_nr
        #:param bit_nr Number of the bit for which the offset is supposed to be calculated
        #:returns offset of the bit
        #:rtype int
        #"""
        #Offset 0 -> 16 - 31
        #Offset 1 ->  0 - 15
        #Offset 2 -> 48 - 63
        #Offset 3 -> 32 - 47
        #Offset 5 -> 64 - 79 
        #(Theoretically 79, but 67 is the highest required bit, therefore offset 4 is not really required)
        #Offset order results from Little Endian 
        if bit_nr >= 16 and bit_nr <= 31:
            return 0
        if bit_nr >= 0 and bit_nr <= 15:
            return 1
        if bit_nr >= 48 and bit_nr <= 63:
            return 2
        if bit_nr >= 32 and bit_nr <= 47:
            return 3
        if bit_nr >= 80 and bit_nr <= 95:
            return 4
        if bit_nr >= 64 and bit_nr <= 79:
            return 5

    def get_bit(self, index, nr):
        #"""Returns bit number which is necessary to acces a specific bit within a word.
        #:param index Index of the addressed module
        #:param nr number of the function, which is required for this bit (see comments in index map)
        #:returns number of the bit
        #:rtype int
        #"""

        # DE
        # Nummer wird Modulo 16 gerechnet, da alle 16 Bit ein neues word anfängt, bei dem wieder mit 0 angefangen wird zu 


        # ENG
        # Number is calculated modulo 16, because every 16 bits a new word starts, where the addressing starts again with 0.
        return self.INDEX.get(index)[nr] % 16
    
    def conveyor_stop(self, conveyor_id):
        # DE
        # Hält das Laufband, welches über conveyor_id angegeben wurde, indem die Bits für Vor- und Rückwärts fahren gelöscht werden.
        # Die analogen Ausgänge, die die speed der Laufbänder steuern, werden nicht verändert.
        # :param conveyor_id der Index des Laufbands als Character (Siehe Hardwaredokumentation Kapitel 2.1.4)

        # ENG
        # Keeps the conveyor specified by conveyor_id by clearing the bits for forward and reverse.
        # The analog outputs that control the speed of the conveyors are not changed.
        # :param conveyor_id the index of the conveyor as character (see hardware documentation chapter 2.1.4)

        with self.sem:
            # DE
            # Nötiger Offset wird berechnet um das korrekte word zu adressieren
            # Da bei den Laufbändern das Bit für Vor/Zurück immer im selben Offset liegen reicht es von einem der Beiden des Offset zu bestimmen

            # ENG
            # Necessary offset is calculated to address the correct word.
            # Since the bit for forward/backward of the tapes are always in the same offset, it is sufficient to determine the offset of one of them

            offset = self.get_offset(self.INDEX.get(conveyor_id)[0])
            bit_forward = self.get_bit(conveyor_id, 0)
            bit_backward = self.get_bit(conveyor_id, 1)

            reg = self.get_output_register(offset)
            # DE
            # Bits für Vor- und Rückwärts fahren löschen damit das Band anhält

            # ENG
            # Delete bits for forward and reverse so that the tape stops
            reg[0] = reset_bit(reg[0], bit_forward)
            reg[0] = reset_bit(reg[0], bit_backward)

            self.set_output_register(reg, offset)

    def conveyor_forward(self, conveyor_id):
        # DE
        # Lässt das Laufband, welches über conveyor_id angegeben wurde, vorwärts fahren, indem das Bit für Vorwärts gesetzt und das Bit für Rückwärts fahren gelöscht wird.
        # Die analogen Ausgänge, die die speed der Laufbänder steuern, werden nicht verändert.
        # :param conveyor_id der Index des Laufbands als Character (Siehe Hardwaredokumentation Kapitel 2.1.4)

        # ENG
        # Makes the conveyor specified by conveyor_id move forward by setting the bit for forward and clearing the bit for reverse.
        # The analog outputs that control the speed of the conveyors are not changed.
        # :param conveyor_id the index of the conveyor as character (see hardware documentation chapter 2.1.4)

        with self.sem:
            # DE
            # #Nötiger Offset wird berechnet um das korrekte word zu adressieren
            # #Da bei den Laufbändern das Bit für Vor/Zurück immer im selben Offset liegen reicht es von einem der Beiden des Offset zu bestimmen

            # ENG
            # #Necessary offset is calculated to address the correct word.
            # #Since the bit for forward/backward of the tapes are always in the same offset, it is sufficient to determine the offset of one of them
            offset = self.get_offset(self.INDEX.get(conveyor_id)[0])
            bit_forward = self.get_bit(conveyor_id, 0)
            bit_backward = self.get_bit(conveyor_id, 1)
            
            reg = self.get_output_register(offset)
            # DE
            # Bit für Vorwärts setzen und Bit für Rückwärts löschen

            # ENG
            # Set bit for forward and clear bit for reverse
            reg[0] = set_bit(reg[0], bit_forward)
            reg[0] = reset_bit(reg[0], bit_backward)

            self.set_output_register(reg, offset)

    def conveyor_backward(self, conveyor_id):
        # DE
        # Lässt das Laufband, welches über conveyor_id angegeben wurde, rückwärts fahren, indem das Bit für Vorwärts gelöscht und das Bit für Rückwärts fahren gesetzt wird.
        # Die analogen Ausgänge, die die speed der Laufbänder steuern, werden nicht verändert.
        # :param conveyor_id der Index des Laufbands als Character (Siehe Hardwaredokumentation Kapitel 2.1.4)

        # ENG
        # Makes the conveyor specified by conveyor_id move backwards by clearing the bit for forward and setting the bit for reverse.
        # The analog outputs that control the speed of the conveyors are not changed.
        # :param conveyor_id the index of the conveyor as character (see hardware documentation chapter 2.1.4)
        with self.sem:
            # DE
            # Nötiger Offset wird berechnet um das korrekte word zu adressieren
            # Da bei den Laufbändern das Bit für Vor/Zurück immer im selben Offset liegen reicht es von einem der Beiden des Offset zu bestimmen
            # ENG
            # Necessary offset is calculated to address the correct word.
            # Since the bit for forward/backward of the tapes are always in the same offset, it is sufficient to determine the offset of one of them
            offset = self.get_offset(self.INDEX.get(conveyor_id)[0])
            bit_forward = self.get_bit(conveyor_id, 0)
            bit_backward = self.get_bit(conveyor_id, 1)
            
            reg = self.get_output_register(offset)
            # DE
            # Bit für Vorwärts löschen und Bit für Rückwärts setzen

            # ENG
            # Clear bit for forward and set bit for reverse
            reg[0] = reset_bit(reg[0], bit_forward)
            reg[0] = set_bit(reg[0], bit_backward)

            self.set_output_register(reg, offset)

    def set_switch(self, weiche_index, pos = 0):
        # DE
        # Stellt die Weiche, die über weiche_index angegeben wurde, auf die Position pos, indem erst alle Bits für die Positionen gelöscht werden und
        # danach das Bit für die Position pos gesetzt wird.
        # :param weiche_index der Index der Weiche als Character (Siehe Hardwaredokumentation Kapitel 2.1.4)
        # :param pos Position auf welche die Weiche gestellt werden (pos = 0 löst Referenzfahrt aus)

        # ENG
        # Sets the switch, which was specified via switch_index, to the position pos, by first clearing all bits for the positions and
        # then setting the bit for position pos.
        # :param switch_index the index of the switch as character (see hardware documentation chapter 2.1.4)
        # :param pos position to which the turnout is set (pos = 0 triggers homing)

        with self.sem:
            # DE
            # Da bei einigene Weichen die Bits zur ansteuerung einer Weiche unterschiedliche Offsets haben muss hier zu jedem Bit der eigene Offset berechnet werden.

            # ENG
            # Since the bits for controlling a turnout have different offsets in some turnouts, the offset must be calculated for each bit.
            offset = [
                self.get_offset(self.INDEX.get(weiche_index)[0]), #Referenz Fahrt
                self.get_offset(self.INDEX.get(weiche_index)[1]), #Position 1
                self.get_offset(self.INDEX.get(weiche_index)[2]), #Position 2
                self.get_offset(self.INDEX.get(weiche_index)[3])  #Position 3
            ]
            bit = [
                self.get_bit(weiche_index, 0), #Referenz Fahrt
                self.get_bit(weiche_index, 1), #Position 1
                self.get_bit(weiche_index, 2), #Position 2
                self.get_bit(weiche_index, 3)  #Position 3
            ]
            #DE
            #Löscht alle Bits zur Weichenstellung (wenn 2 oder mehr Bits gleichzeitig gesetzt wären, wäre nicht eindeutig welche Position die weiche einnehmen soll)

            #ENG
            #Clears all bits for switch setting (if 2 or more bits were set at the same time, it would not be clear which position the switch should take)
            for i in range(4):
                reg = self.get_output_register(offset=offset[i])
                reg[0] = reset_bit(reg[0], bit[i])
                self.set_output_register(reg, offset=offset[i])

            #DE
            #Setzt das Bit, dass die Weiche an die Position pos fährt

            #ENG
            #Sets the bit that the switch moves to position pos
            reg = self.get_output_register(offset=offset[pos])
            reg[0] = set_bit(reg[0], bit[pos])
            self.set_output_register(reg, offset=offset[pos])

    def check_conveyor_workpiece_begin(self, conveyor_id):
        #DE
        #Überprüft, ob der Sensor am Anfang des Laufbandes, welches mit conveyor_id angegeben wurde, ein Werkstück erkennt.
        #:param conveyor_id der Index des Laufbands als Character (Siehe Hardwaredokumentation Kapitel 2.1.4)
        #:returns boolean ob der Sensor ein Werkstück erkennt
        #:rtype bool

        #ENG
        #Checks if the sensor detects a workpiece at the beginning of the conveyor specified by conveyor_id.
        #:param conveyor_id the index of the conveyor as character (see hardware documentation chapter 2.1.4)
        #:returns boolean whether the sensor detects a workpiece
        #:rtype bool

        offset = self.get_offset(self.INDEX.get(conveyor_id)[0])
        bit_sensor_anfang = self.get_bit(conveyor_id, 0)

        return test_bit(self.get_input_register(offset)[0], bit_sensor_anfang)

    def check_conveyor_workpiece_end(self, conveyor_id):
        #DE
        #Überprüft, ob der Sensor am Ende des Laufbandes, welches mit conveyor_id angegeben wurde, ein Werkstück erkennt.
        #:param conveyor_id der Index des Laufbands als Character (Siehe Hardwaredokumentation Kapitel 2.1.4)
        #:returns boolean ob der Sensor ein Werkstück erkennt
        #:rtype bool

        #ENG
        #Checks if the sensor detects a workpiece at the end of the conveyor specified by conveyor_id.
        #:param conveyor_id the index of the conveyor as character (see hardware documentation chapter 2.1.4)
        #:returns boolean whether the sensor detects a workpiece
        #:rtype bool

        
        offset = self.get_offset(self.INDEX.get(conveyor_id)[1])
        bit_sensor_ende = self.get_bit(conveyor_id, 1)

        return test_bit(self.get_input_register(offset)[0], bit_sensor_ende)

    def check_switch_position_reached(self, weiche_index):
        #DE
        #Überprüft, ob die Weiche, welche mit weiche_index angegeben wurde, die gewünschte Position erreicht hat.
        #:param weiche_index der Index der Weiche als Character (Siehe Hardwaredokumentation Kapitel 2.1.4)
        #:returns boolean ob die weiche die Position erreicht hat
        #:rtype bool

        #ENG
        #Checks if the turnout specified with turnout_index has reached the desired position.
        #:param weiche_index the index of the turnout as character (see hardware documentation chapter 2.1.4)
        #:returns boolean if the switch has reached the position
        #:rtype bool

        offset = self.get_offset(self.INDEX.get(weiche_index)[0])
        bit_pos_erreicht = self.get_bit(weiche_index, 0)

        return test_bit(self.get_input_register(offset)[0], bit_pos_erreicht)

    def check_switch_in_movement(self, weiche_index):
        #DE
        #Überprüft, ob die Weiche, welche mit weiche_index angegeben wurde, in Bewegung ist.
        #:param weiche_index der Index der Weiche als Character (Siehe Hardwaredokumentation Kapitel 2.1.4)
        #:returns boolean ob die Weiche in Bewegung ist
        #:rtype bool

        #ENG
        #Checks if the turnout specified with turnout_index is in motion.
        #:param turnout_index the index of the turnout as character (see hardware documentation chapter 2.1.4)
        #:returns boolean whether the switch is in motion
        #:rtype bool
       
        offset = self.get_offset(self.INDEX.get(weiche_index)[1])
        bit_in_bewegung = self.get_bit(weiche_index, 1)

        return test_bit(self.get_input_register(offset)[0], bit_in_bewegung)

    def check_switch_workpiece(self, weiche_index):
        
        #DE
        #Überprüft, ob sich in der Weiche, welche mit weiche_index angegeben wurde, ein Werkstueck befindet.
        #:param weiche_index der Index der Weiche als Character (Siehe Hardwaredokumentation Kapitel 2.1.4)
        #:returns boolean ob sich in der Weiche ein Werkstueck befindet
        #:rtype bool      

        #ENG
        #Checks if there is a workpiece in the turnout specified with turnout_index.
        #:param weiche_index the index of the turnout as character (see hardware documentation chapter 2.1.4)
        #:returns boolean whether there is a workpiece in the switch
        #:rtype bool
    
        offset = self.get_offset(self.INDEX.get(weiche_index)[2])
        bit_werkstueck = self.get_bit(weiche_index, 2)

        return test_bit(self.get_input_register(offset)[0], bit_werkstueck)

    def check_switch_in_reference_position(self, weiche_index):

        #DE
        #Überprüft das Bit für die Referenzposition, kann aber nicht verwendet werden um Ende der Referenzfahrt zu ermitteln.
        #Methode wurde nur Vollständigkeitshalber implementiert.
        #:param weiche_index der Index der Weiche als Character (Siehe Hardwaredokumentation Kapitel 2.1.4)
        #:returns boolean das Bit für die Referenzposition gesetzt ist
        #:rtype bool

        #ENG
        #Checks the bit for the reference position, but cannot be used to determine the end of the reference run.
        #Method was implemented only for completeness.
        #:param turnout_index the index of the turnout as character (see hardware documentation chapter 2.1.4)
        #:returns boolean the bit for the reference position is set
        #:rtype bool

        offset = self.get_offset(self.INDEX.get(weiche_index)[3])
        bit_referenzposition = self.get_bit(weiche_index, 3)

        return test_bit(self.get_input_register(offset)[0], bit_referenzposition)

    def check_sensor_conveyor_workstations_back(self, conveyor_id):
        
        #DE
        #Überprüft, ob von dem Sensor hinter dem Auswurf der Bearbeitungsstation ein Werkstück erkannt wird.
        #:param conveyor_id der Index des Laufbands als Character (Nur B und R haben diese Sensoren! Siehe Hardwaredokumentation Kapitel 2.1.4)
        #:returns boolean ob von dem Sensor ein Werkstück erkannt wird
        #:rtype bool

        #ENG
        #Checks whether a workpiece is detected by the sensor behind the ejector of the processing station.
        #:param conveyor_id the index of the conveyor as character (Only B and R have these sensors! See hardware documentation chapter 2.1.4)
        #:returns boolean whether a workpiece is detected by the sensor
        #:rtype bool

        offset = self.get_offset(self.INDEX.get(conveyor_id)[2])
        bit_werkstueck_hinten = self.get_bit(conveyor_id, 2)

        return test_bit(self.get_input_register(offset)[0], bit_werkstueck_hinten)

    def check_sensor_conveyor_workstations_front(self, conveyor_id):
        
        #DE
        #Überprüft, ob von dem Sensor vor dem Auswurf der Bearbeitungsstation ein Werkstück erkannt wird.
        #:param conveyor_id der Index des Laufbands als Character (Nur B und R haben diese Sensoren! Siehe Hardwaredokumentation Kapitel 2.1.4)
        #:returns boolean ob von dem Sensor ein Werkstück erkannt wird
        #:rtype bool

        #ENG
        #Checks if a workpiece is detected by the sensor before the ejection of the processing station.
        #:param conveyor_id the index of the conveyor as character (Only B and R have these sensors! See hardware documentation chapter 2.1.4)
        #:returns boolean whether a workpiece is detected by the sensor
        #:rtype bool

        offset = self.get_offset(self.INDEX.get(conveyor_id)[3])
        bit_werkstueck_hinten = self.get_bit(conveyor_id, 3)

        return test_bit(self.get_input_register(offset)[0], bit_werkstueck_hinten)

    def update_conveyor_speed(self):
        
        #DE
        #Setzt die Analogen Ausgänge zum regeln der Laufbandspeed auf die Werte, die in der Map self.conveyor_speed angegeben werden.

        #ENG
        #Sets the analog outputs for controlling the conveyor speed to the values specified in the map self.conveyor_speed.

        with self.read_write_sem:

            #DE
            #Automatisches öffnen und schließen von TCP verbindungen aufheben, da hier viele TCP Pakete nacheinander gesendet werden
            #und es somit besser ist einmal die Verbindung zu öffnen und danach wieder zu schließen.

            #ENG
            #Override automatic opening and closing of TCP connections, because many TCP packets are sent one after the other.
            #and therefore it is better to open the connection once and then close it again.

            self.client.auto_close = False
            self.client.auto_open = False
            
            #DE
            #Öffnen der TCP Verbindung
            
            #ENG
            #Open the TCP connection

            self.client.open()

            self.client.write_single_register(8024, int("0x6000",16))
            self.client.write_single_register(8024, int("0x3000",16))

            self.client.write_single_register(8025, self.conveyor_speed.get('A'))
            self.client.write_single_register(8026, self.conveyor_speed.get('B'))
            self.client.write_single_register(8027, self.conveyor_speed.get('C'))
            self.client.write_single_register(8028, self.conveyor_speed.get('D'))

            self.client.write_single_register(8024, int("0x0100",16))
            self.client.write_single_register(8024, int("0x0b00",16))

            self.client.write_single_register(8025, self.conveyor_speed.get('H'))
            self.client.write_single_register(8026, self.conveyor_speed.get('I'))
            self.client.write_single_register(8027, self.conveyor_speed.get('J'))
            self.client.write_single_register(8028, self.conveyor_speed.get('L'))

            self.client.write_single_register(8024, int("0x0900",16))


            self.client.write_single_register(8029, int("0x6000",16))
            self.client.write_single_register(8029, int("0x3000",16))

            self.client.write_single_register(8030, self.conveyor_speed.get('M'))
            self.client.write_single_register(8031, self.conveyor_speed.get('P'))
            self.client.write_single_register(8032, self.conveyor_speed.get('Q'))
            self.client.write_single_register(8033, self.conveyor_speed.get('R'))

            self.client.write_single_register(8029, int("0x0100",16))
            self.client.write_single_register(8029, int("0x0b00",16))

            self.client.write_single_register(8030, self.conveyor_speed.get('U'))
            self.client.write_single_register(8031, self.conveyor_speed.get('V'))
            self.client.write_single_register(8032, 0)
            self.client.write_single_register(8033, 0)

            self.client.write_single_register(8029, int("0x0900",16))
            
            #DE
            #Schließen der TCP Verbindung

            #ENG
            #Close the TCP connection

            self.client.close()

            self.client.auto_close = True
            self.client.auto_open = True

    def set_conveyor_speed(self, conveyor_id, speed):
        
        #DE
        #Setzt die speed eines Laufbands auf den übergebenen Wert.
        #:param conveyor_id Index als Character des Laufbands, dessen speed gesetzt werden soll (Siehe Hardwaredokumentation Kapitel 2.1.3)
        #:param speed speed des Laufbandes als Integer zwischen 0 (0%/0V) und 30000 (100%/10V)

        #ENG
        #Sets the speed of a conveyor to the given value.
        #:param conveyor_id Index as character of the conveyor whose speed should be set (see hardware documentation chapter 2.1.3)
        #:param speed speed of the conveyor as integer between 0 (0%/0V) and 30000 (100%/10V)

        with self.sem:
            self.conveyor_speed[conveyor_id] = speed
            self.update_conveyor_speed()

    def set_conveyor_speed_all(self, speed):

        # DE
        # Setzt die speed aller Laufbänder auf den übergebenen Wert.
        # :param speed speed der Laufbänder als Integer zwischen 0 (0%/0V) und 30000 (100%/10V)

        # ENG
        # Sets the speed of all treadmills to the given value.
        # :param speed speed of the treadmills as integer between 0 (0%/0V) and 30000 (100%/10V).

        with self.sem:
            for i in self.INDEX_CONVEYORS:
                self.conveyor_speed[i] = speed
            self.update_conveyor_speed()
