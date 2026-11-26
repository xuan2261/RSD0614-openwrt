# SPDX-License-Identifier: GPL-2.0-only
include $(TOPDIR)/rules.mk
include $(INCLUDE_DIR)/kernel.mk

PKG_NAME:=rtl8192cd-rsd0614
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only
PKG_MAINTAINER:=Rock Space RSD0614 V1.0 OpenWrt RAM-Boot Port

include $(INCLUDE_DIR)/package.mk

define KernelPackage/rtl8192cd-rsd0614
  SUBMENU:=Wireless Drivers
  TITLE:=Realtek RTL8197G (2.4 GHz) + RTL8814BR (5 GHz) dual-band driver for RSD0614 V1.0
  DEPENDS:=@TARGET_realtek_rtl8197f
  FILES:=$(PKG_BUILD_DIR)/rtl8192cd.ko
  KCONFIG:=CONFIG_WIRELESS=y
  AUTOLOAD:=$(call AutoLoad,60,rtl8192cd)
endef

define KernelPackage/rtl8192cd-rsd0614/description
 Pinned Realtek SDK v3.6.0 rtl8192cd dual-band driver ported to Linux 4.14.187
 for Rock Space RSD0614 V1.0: on-SoC RTL8197G 2.4 GHz WMAC (wlan1, IRQ 6) and
 PCIe0 RTL8814BR 5 GHz 4x4 radio (wlan0, 10ec:b814, IRQ 5), using WEXT +
 in-kernel WPA2-PSK and read-only runtime /dev/mtd1 "cfg" calibration loading.
endef

define Build/Prepare
	$(RM) -r $(PKG_BUILD_DIR)
	$(INSTALL_DIR) $(PKG_BUILD_DIR)
	$(CP) ./src/. $(PKG_BUILD_DIR)/
	for d in WlanHAL/Data/8197G WlanHAL/Data/8814B; do \
		for f in "$(PKG_BUILD_DIR)/$$d"/*.txt "$(PKG_BUILD_DIR)/$$d"/*.bin "$(PKG_BUILD_DIR)/$$d"/*.BIN; do \
			[ -f "$$f" ] || continue; \
			base="$$(basename "$$f")"; \
			stem="$${base%.*}"; \
			perl "$(PKG_BUILD_DIR)/bin2c.pl" "data_$$stem" < "$$f" > "$(PKG_BUILD_DIR)/data_$$stem.c"; \
		done; \
	done
	find $(PKG_BUILD_DIR) -maxdepth 1 -type f -name 'data_*.c' -exec touch {} +
endef

RTL8192CD_RSD0614_VARS:= \
	CONFIG_RTL8192CD=m \
	CONFIG_WIRELESS_LAN_MODULE=y \
	CONFIG_WIFI_HCI=y \
	CONFIG_PCI_HCI=y \
	CONFIG_NET_PCI=y \
	CONFIG_WLAN_HAL=y \
	CONFIG_WLAN_HAL_88XX=y \
	CONFIG_RTL_8197F=y \
	CONFIG_RTL_8197F_VG=y \
	CONFIG_RTL_ODM_WLAN_DRIVER=y \
	CONFIG_WLAN_MACHAL_API=y \
	CONFIG_WLAN_MACHAL_API_V1=y \
	CONFIG_OPENWRT_SDK=y \
	CONFIG_RTL8192CD_LINUX6_BUS=y \
	CONFIG_MW5_FORCE_WLAN_DEVICE_TABLE=y \
	CONFIG_MW5_LEGACY_WEXT=y \
	CONFIG_RTL_COMAPI_WLTOOLS=y \
	CONFIG_RTL_COMAPI_CFGFILE=y \
	CONFIG_RTL_CLIENT_MODE_SUPPORT=y \
	CONFIG_RTL_REPEATER_MODE_SUPPORT=y \
	CONFIG_VXD_DIFF_MAC=y \
	CONFIG_RTL_WDS_SUPPORT=n \
	CONFIG_RTL_MESH_SUPPORT=n \
	CONFIG_RTL_MESH_SINGLE_IFACE=n \
	CONFIG_WLAN_HAL_8197G=y \
	CONFIG_BAND_5G_ON_WLAN0=y \
	CONFIG_SOC_WIFI=y \
	CONFIG_WLAN_HAL_8814BE=y \
	CONFIG_RTL_8814B_SUPPORT=y \
	CONFIG_RTL_92F_SUPPORT=n \
	CONFIG_RTL_SHRINK_MEMORY_SIZE=y \
	CONFIG_PHY_EAT_40MHZ=y

define Build/Compile
	+$(KERNEL_MAKE) M="$(PKG_BUILD_DIR)" \
		$(RTL8192CD_RSD0614_VARS) \
		KCFLAGS="-I$(LINUX_DIR) -I$(LINUX_DIR)/arch/mips/include/asm/mach-rtl8197f -I$(PKG_BUILD_DIR) -include $(PKG_BUILD_DIR)/rtl8197f_linux_compat.h -Wno-error -Wno-implicit-function-declaration -Wno-int-conversion -Wno-incompatible-pointer-types" \
		modules
endef

$(eval $(call KernelPackage,rtl8192cd-rsd0614))
