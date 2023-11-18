#----------------------------------------------
# Packet comparator.
#----------------------------------------------

class comp:

    def __init__(self, name='comparator'):
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
                assert False , f"[TEST_FALIED] Packets are not equal"
            else:
                print(f"[TEST_PASSED] Packet are equal. Congradulations!")

class predictor:

    def __init__(self, name='comparator'):
        self.name = name
        self.port_in = []
        self.port_out = []
        
    def predict(self):
        '''Override the method to convert one type of packet 
        to another'''
        for pkt in port_in:
            port_out.append(pkt)
        
