# Sermatec Inverter for Home Assistant

## Installation
### Manual
1. Download integration.
2. Copy the folder `custom_components/sermatec_inverter` to your config directory.
3. Restart Home Assistant.
4. In Home Assistant, go to Settings -> Devices & Services -> `+ ADD INTEGRATION` -> search for Sermatec Inverter -> fill in host and port -> click submit.
5. Done! Now you can see all the sensors in Integrations under Sermatec Inverter.

Notes:
- IP is probably assigned dynamically by your router's DHCP server. I recommend setting a static IP (available on most routers), otherwise you would probably need to change the IP in the config once in a while.
- The default port is `8899`.

### Supported devices
Only tested device is the `Sermatec SMT-10K-TL-TH`. However, probably all residential hybrid inverters by Sermatec should work.

### Communication script
Inverter communication script is in development in [this repository](https://github.com/andreondra/sermatec-inverter), which includes also a detailed documentation.

## Disclaimer
Because the protocol used for local communication is reverse-engineered (due to the lack of the official documentation,) I am not responsible for any damage that this integration could cause to your inverter or to your house wiring / electrical equipment.