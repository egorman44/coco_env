#----------------------------------------------
# Packet comparator.
#----------------------------------------------

class Comparator:

    def __init__(self, name):
        self.name = name
        self.port_prd = []
        self.port_out = []
        
    def compare(self):
        print(f"{self.name} statistics:")
        print(f"\t Num of prd tnx: {len(self.port_prd)}")
        print(f"\t Num of out tnx: {len(self.port_out)}")
        if len(self.port_prd) != len(self.port_out):
            assert False , f"[TEST_FALIED] Number of transactions are not equal. \n\t len(port_prd) = {len(self.port_prd)} \n\t len(port_out) = {len(self.port_out)}"
        for indx in range (0,len(self.port_prd)):
            if(self.port_out[indx].compare(self.port_prd[indx])):
                self.port_out[indx].print_pkt()
                self.port_prd[indx].print_pkt()
                assert False , f"[TEST_FALIED] Packets are not equal"
            else:
                print(f"\n[TEST_PASSED] Packets are equal. Congradulations!\n")

class Predictor:

    def __init__(self, name, port_prd):
        self.name = name
        self.port_in = []
        self.port_prd = port_prd
        
    def predict(self):
        '''Override the method to convert one type of packet 
        to another'''
        for pkt in self.port_in:
            self.port_prd.append(pkt)
        
