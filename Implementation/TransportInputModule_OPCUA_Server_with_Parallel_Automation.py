import sys
import time
import logging
import threading

from TransportInputModule_Library import *
from pyModbusTCP.client import ModbusClient
from asyncua.sync import Server
from asyncua import ua

#declare module

TIM = TransportInputModule_Library("192.168.200.235")

def conveyor_move_forward(node):
    globals() [f"TIM_Conveyor_is_move"].write_value(True) 
    TIM.set_conveyor_speed_all(30000) 
    for conveyor_id in ['A', 'B', 'C', 'D', 'H' , 'I', 'J', 'L', 'M', 'P', 'Q', 'R', 'U', 'V']:
        TIM.conveyor_forward(conveyor_id)

def conveyor_stop(node):
    globals() [f"TIM_Conveyor_is_move"].write_value(False) 
    for conveyor_id in ['A', 'B', 'C', 'D', 'H' , 'I', 'J', 'L', 'M', 'P', 'Q', 'R', 'U', 'V']:
        TIM.conveyor_stop(conveyor_id)

def reset_switch(node):
    print("reset switch") 
    for switch_id in ['N','T','F','W','E','G','K','S','O']:
        TIM.set_switch(switch_id,pos=0)

def test_server(node):
    print("Server is OK")

def check_workpiece_end_of_conveyor(conveyor_name, switch_name, next_conveyor_name, switch_pre_pos, switch_post_pos):

    while not TIM.check_conveyor_workpiece_end(conveyor_name):
        sleep(0.05)
    TIM.set_switch(switch_name, pos=switch_pre_pos)
    globals()[f"workpiece_at_conveyor_{conveyor_name}"].write_value(False)

    while not TIM.check_switch_position_reached(switch_name):
        sleep(0.05)
    globals()[f"position_of_switch_{switch_name}"].write_value(switch_pre_pos)

    while not TIM.check_switch_workpiece(switch_name):
        sleep(0.05)
    TIM.set_switch(switch_name, pos=switch_post_pos)
    sleep(0.05)
    globals()[f"position_of_switch_{switch_name}"].write_value(switch_post_pos)
    sleep(0.05)
    globals()[f"workpiece_at_conveyor_{next_conveyor_name}"].write_value(True)

def main ():

    # Create a logger    
    _logger = logging.getLogger(__name__)

    # setup our server
    server = Server()
    server.set_endpoint("opc.tcp://192.168.200.191:4840/freeopcua/server/")
    
    # setup our own namespace, not really necessary but should as spec
    uri = "http://examples.freeopcua.github.io"
    idx = server.register_namespace(uri)

    # get Objects node, this is where we should put our nodes
    objects = server.nodes.objects

    #TIM_testvariable
    TIM_Server = objects.add_object(idx, "TIM_Server")
    TIM_Server_testvar = TIM_Server.add_variable(idx, "Test_Variable", 1.0)
    globals() [f"TIM_Conveyor_is_move"] = TIM_Server.add_variable(idx, "TIM_Conveyor_is_move", False , datatype=ua.NodeId(ua.ObjectIds.Boolean))

    #TIM_method
    TIM_Server.add_method(ua.NodeId("Conveyor_Move_Forward", idx), ua.QualifiedName("Conveyor_Move_Forward", idx), conveyor_move_forward)
    TIM_Server.add_method(ua.NodeId("Conveyor_Stop", idx), ua.QualifiedName("Conveyor_Stop", idx), conveyor_stop)
    TIM_Server.add_method(ua.NodeId("Reset_All_Switch", idx), ua.QualifiedName("Reset_All_Switch", idx), reset_switch)
    TIM_Server.add_method(ua.NodeId("Test_Server", idx), ua.QualifiedName("Test_Server", idx), test_server)

    #Switch
    switch_names = ['E', 'F', 'G', 'K', 'N', 'O', 'S', 'T', 'W']
    for amounth_of_switch in switch_names:
        switch_node = server.nodes.objects.add_object(idx, f"switch_{amounth_of_switch}")
        switch_variable = switch_node.add_variable(idx, f"position_of_switch_{amounth_of_switch}", 0, datatype=ua.NodeId(ua.ObjectIds.Int64))
        globals()[f"position_of_switch_{amounth_of_switch}"] = switch_variable

    #Conveyor
    conveyor_names = ['A', 'B', 'C', 'D', 'H', 'I', 'J', 'M', 'P', 'Q', 'R', 'U', 'V', 'L' ]
    for amounth_of_conveyer in conveyor_names:
        conveyor_node = server.nodes.objects.add_object(idx, f"conveyor_{amounth_of_conveyer}")
        conveyor_variable = conveyor_node.add_variable(idx, f"workpiece_at_conveyor_{amounth_of_conveyer}", False, datatype=ua.NodeId(ua.ObjectIds.Boolean))
        globals()[f"workpiece_at_conveyor_{amounth_of_conveyer}"] = conveyor_variable

    #Server start
    server.start()
    while True:
        sleep(0.5)
        new_val = TIM_Server_testvar.get_value() + 0.1
        _logger.info("Set value of %s to %.1f", TIM_Server_testvar, new_val)
        TIM_Server_testvar.write_value(new_val)

        # Run check_workpiece_end_of_conveyor in separate threads
        conveyor_data = [
            ("L", "N", "Q", 3, 1),
            ("Q", "T", "H", 3, 1),
            ("H", "F", "D", 3, 1),
            ("D", "W", "A", 3, 2),
            ("A", "E", "B", 3, 2),
            ("B", "G", "I", 3, 1),
            ("I", "K", "R", 1, 3),
            ("R", "S", "P", 2, 1),
            ("P", "O", "L", 1, 3)
        ]
        threads = []

        for data in conveyor_data:
            thread = threading.Thread(target=check_workpiece_end_of_conveyor, args=data)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
   
if __name__ == "__main__":

    main()