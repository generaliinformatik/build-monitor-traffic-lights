import avea
import time

bulbaddrgruen = "7c:ec:79:d7:6b:42"
bulbaddrrot = "84:eb:18:66:04:75"
bulbaddrgelb = "7c:ec:79:d7:b9:83"

bulbrot = avea.Bulb(bulbaddrrot)
print(bulbrot.get_name())
bulbrot.set_brightness(4095)

bulbgelb = avea.Bulb(bulbaddrgelb)
print(bulbgelb.get_name())
bulbgelb.set_brightness(4095)

bulbgruen = avea.Bulb(bulbaddrgruen)
print(bulbgruen.get_name())
bulbgruen.set_brightness(4095)
