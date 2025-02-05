from tidal import *
import network
import settings
import wifi
from wifi import WIFI_AUTH_OPEN, WIFI_AUTH_WPA2_PSK, WIFI_AUTH_WPA2_ENTERPRISE
from app import MenuApp

class WifiClient(MenuApp):
    
    TITLE = "Wi-Fi Connnect"

    def make_join_fn(self, idx):
        # I will never get on with how Python does variable capture...
        def fn():
            self.join_index(idx)
        return fn

    def update_ui(self, redraw=True):
        choices = []
        title = self.TITLE
        if wifi.status():
            title += f"\n{wifi.get_ssid()}\n{wifi.get_ip()}"
            choices.append(("[Disconnect]", self.disconnect))
        elif self.connecting is not None:
            title += f"\nConnecting to\n{wifi.get_ssid()}..."
            choices.append(("[Cancel]", self.disconnect))

        if wifi.get_sta_status() != network.STAT_CONNECTING:
            for i, (ssid, _) in enumerate(self.wifi_networks):
                choices.append((ssid, self.make_join_fn(i)))
            choices.append(("[Rescan]", self.scan))
        self.window.set(title, choices, redraw=redraw)

    def scan(self):
        self.window.set_choices(None)
        self.window.set_title(self.TITLE)
        self.window.println("Scanning...", 0)
        self.window.clear_from_line(1)
        self.wifi_networks = []
        for ap in wifi.scan():
            print(f"Found {ap}")
            if ap[0]:
                authmode = ap[4]
                try:
                    self.wifi_networks.append((ap[0].decode("utf-8"), authmode))
                except:
                    # Ignore any APs that don't decode as valid UTF-8
                    pass
        self.update_ui()

    def on_start(self):
        super().on_start()
        self.wifi_networks = []
        if ssid := wifi.get_default_ssid():
            if wifi.get_default_username():
                authmode = WIFI_AUTH_WPA2_ENTERPRISE
            elif wifi.get_default_password():
                authmode = WIFI_AUTH_WPA2_PSK # doesn't matter exactly so long as it's not enterprise or open
            else:
                authmode = WIFI_AUTH_OPEN
            self.wifi_networks.append((ssid, authmode))
        self.connecting = None
        self.connection_timer = None

    def on_activate(self):
        self.update_ui(redraw=False)
        super().on_activate()

    def on_deactivate(self):
        super().on_deactivate()
        if self.connection_timer:
            self.connection_timer.cancel()
            self.connection_timer = None

        if not wifi.status():
            # If we're not connected, stop preventing sleep
            wifi.stop()

    def join_index(self, i):
        (ssid, authmode) = self.wifi_networks[i]
        username = None
        password = None
        if authmode:
            if ssid == wifi.DEFAULT_SSID:
                # Extra special case, in case a different network has been connected to and is now the default
                username = wifi.DEFAULT_USERNAME
                password = wifi.DEFAULT_PASSWORD
            elif ssid == wifi.get_default_ssid():
                username = wifi.get_default_username()
                password = wifi.get_default_password()
            else:
                if authmode == WIFI_AUTH_WPA2_ENTERPRISE:
                    username = self.keyboard_prompt("Enter username:")
                password = self.keyboard_prompt("Enter password:")
        return self.join_wifi(ssid, password, username)

    def join_wifi(self, ssid, password, username=None):
        self.window.set_choices(None)
        self.username = username
        self.password = password
        wifi.connect(ssid, password, username)
        self.connecting = wifi.get_connection_timeout()
        self.connection_timer = self.periodic(1000, self.update_connection)
        self.update_ui()

    # This can also cancel when mid-connecting
    def disconnect(self):
        self.cancel_timer()
        wifi.disconnect()
        self.update_ui()

    def cancel_timer(self):
        if self.connection_timer:
            self.connection_timer.cancel()
            self.connection_timer = None
        self.connecting = None

    def update_connection(self):
        self.connecting -= 1
        if self.connecting <= 0:
            # We've timed out, even if the connection isn't showing an error,
            # which it won't without having set
            # WLAN.config(reconnects=...)
            print("Connection attempt timed out")
            self.disconnect()
            return

        status = wifi.get_sta_status()
        if status == network.STAT_CONNECTING:
            return
        elif status == network.STAT_GOT_IP:
            wifi.save_defaults(wifi.get_ssid(), self.password, self.username)
            # The update_ui call will take care of everything else

        self.cancel_timer()
        self.update_ui()
