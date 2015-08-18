#include "debug.h"
#include "../../common/native_wuclasses/native_wuclasses.h"
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "../../../../../config/galileo/c/config.h"

void wuclass_touch_sensor_setup(wuobject_t *wuobject) {
    #ifdef INTEL_GALILEO_GEN1
    #endif
    #ifdef INTEL_GALILEO_GEN2
    //Configure IO4 shield pin as a GPIO Input.
    if( access( "/sys/class/gpio/gpio6/value", F_OK ) == -1 ) {
	system("echo -n 6 > /sys/class/gpio/export");
    }
    if( access( "/sys/class/gpio/gpio36/value", F_OK ) == -1 ) {
	system("echo -n 36 > /sys/class/gpio/export");
    }
    if( access( "/sys/class/gpio/gpio37/value", F_OK ) == -1 ) {
	system("echo -n 37 > /sys/class/gpio/export");
    }
    system("echo in > /sys/class/gpio/gpio6/direction");
    system("echo strong > /sys/class/gpio/gpio37/drive");
    system("echo in > /sys/class/gpio/gpio36/direction");
    #endif
    #ifdef INTEL_EDISON
    //Configure IO4 shield pin as a GPIO Input.
    if( access( "/sys/class/gpio/gpio129/value", F_OK ) == -1 ) {
	system("echo -n 129 > /sys/class/gpio/export");
    }
    if( access( "/sys/class/gpio/gpio252/value", F_OK ) == -1 ) {
	system("echo -n 252 > /sys/class/gpio/export");
    }
    if( access( "/sys/class/gpio/gpio220/value", F_OK ) == -1 ) {
	system("echo -n 220 > /sys/class/gpio/export");
    }
    if( access( "/sys/class/gpio/gpio214/value", F_OK ) == -1 ) {
	system("echo -n 214 > /sys/class/gpio/export");
    }
    system("echo low > /sys/class/gpio/gpio214/direction");
    system("echo low > /sys/class/gpio/gpio252/direction");
    system("echo in > /sys/class/gpio/gpio220/direction");
    system("echo mode0 > /sys/kernel/debug/gpio_debug/gpio129/current_pinmux");
    system("echo in > /sys/class/gpio/gpio129/direction");
    system("echo high > /sys/class/gpio/gpio214/direction");
    #endif
}

void wuclass_touch_sensor_update(wuobject_t *wuobject) {
    bool value;
    int value_i;
    FILE *fp = NULL;
    #ifdef INTEL_GALILEO_GEN1
    #endif
    #ifdef INTEL_GALILEO_GEN2 
    while (fp == NULL)
      fp = fopen("/sys/class/gpio/gpio6/value", "r");
    #endif
    #ifdef INTEL_EDISON
    while (fp == NULL)
      fp = fopen("/sys/class/gpio/gpio129/value", "r");
    #endif
    fscanf(fp, "%d", &value_i);
    fclose(fp);
    value = (value_i != 0);
    DEBUG_LOG(DBG_WKPFUPDATE, "WKPFUPDATE(Touch Sensor): Sensed binary value: %d\n", value); 
    wkpf_internal_write_property_boolean(wuobject, WKPF_PROPERTY_TOUCH_SENSOR_CURRENT_VALUE, value);
}
