#!/system/bin/sh
# Naz Android Toolkit - Permanent Identity Fix
exec > /data/local/tmp/nat_fix.log 2>&1
echo 'NAT Fix: Script started'
sleep 30
if [ "$(getprop persist.sys.safemode)" = "1" ] || [ "$(getprop ro.boot.safemode)" = "1" ]; then
    echo 'NAT Fix: Safe Mode detected, aborting.'
    exit 0
fi
until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 2; done
echo 'NAT Fix: Applying properties...'
resetprop -n ro.product.brand "realme"
resetprop -n ro.product.manufacturer "realme"
resetprop -n ro.product.model "Realme 7i"
resetprop -n ro.product.name "RMX2103"
resetprop -n ro.product.device "RE50C1"
resetprop -n ro.build.product "RMX2103"
resetprop -n ro.product.system.brand "realme"
resetprop -n ro.product.system.manufacturer "realme"
resetprop -n ro.product.system.model "Realme 7i"
resetprop -n ro.product.system.name "RMX2103"
resetprop -n ro.product.system.device "RE50C1"
resetprop -n ro.system.product.manufacturer "realme"
resetprop -n ro.system.product.brand "realme"
resetprop -n ro.product.vendor.brand "realme"
resetprop -n ro.product.vendor.manufacturer "realme"
resetprop -n ro.product.vendor.model "Realme 7i"
resetprop -n ro.product.vendor.name "RMX2103"
resetprop -n ro.product.vendor.device "RE50C1"
resetprop -n ro.product.product.brand "realme"
resetprop -n ro.product.product.manufacturer "realme"
resetprop -n ro.product.product.model "Realme 7i"
resetprop -n ro.product.product.name "RMX2103"
resetprop -n ro.product.product.device "RE50C1"
resetprop -n ro.product.system_ext.brand "realme"
resetprop -n ro.product.system_ext.manufacturer "realme"
resetprop -n ro.product.system_ext.model "Realme 7i"
resetprop -n ro.product.system_ext.name "RMX2103"
resetprop -n ro.product.system_ext.device "RE50C1"
resetprop -n ro.product.odm.brand "realme"
resetprop -n ro.product.odm.manufacturer "realme"
resetprop -n ro.product.odm.model "Realme 7i"
resetprop -n ro.product.odm.name "RMX2103"
resetprop -n ro.product.odm.device "RE50C1"
resetprop -n ro.product.bootimage.brand "realme"
resetprop -n ro.product.bootimage.manufacturer "realme"
resetprop -n ro.product.bootimage.model "Realme 7i"
resetprop -n ro.product.bootimage.name "RMX2103"
resetprop -n ro.product.bootimage.device "RE50C1"
resetprop -n ro.build.description "RMX2103-user 11 RKQ1.201217.002 1657488232232 release-keys"
resetprop -n ro.build.fingerprint "realme/RMX2103/RE50C1:11/RKQ1.201217.002/1657488232232:user/release-keys"
resetprop -n ro.system.build.fingerprint "realme/RMX2103/RE50C1:11/RKQ1.201217.002/1657488232232:user/release-keys"
resetprop -n ro.vendor.build.fingerprint "realme/RMX2103/RE50C1:11/RKQ1.201217.002/1657488232232:user/release-keys"
resetprop -n ro.product.build.fingerprint "realme/RMX2103/RE50C1:11/RKQ1.201217.002/1657488232232:user/release-keys"
resetprop -n ro.system_ext.build.fingerprint "realme/RMX2103/RE50C1:11/RKQ1.201217.002/1657488232232:user/release-keys"
resetprop -n ro.odm.build.fingerprint "realme/RMX2103/RE50C1:11/RKQ1.201217.002/1657488232232:user/release-keys"
echo 'NAT Fix: All properties applied successfully.'