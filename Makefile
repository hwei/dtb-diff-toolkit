
# https://github.com/rockchip-linux/kernel 源码目录
KERNEL_DIR := ../kernel
# kernel 源码中的 dts 文件目录
VERIFY_DTS_DIR := $(KERNEL_DIR)/arch/arm64/boot/dts/rockchip

# 从 kernel 源码中验证 phandle_property_defines.csv 的 dts 文件名列表
VERIFY_DTS_NAME_LIST := rk3399-sapphire-excavator-edp.dts rk3399-sapphire-excavator-linux.dts

# 输入数据放到下面这两个目录中：

# 存放 dump 出来的 .dtb 文件的目录
DUMP_DIR := ./dump
# 存放 dump 出来魔改过的 .rb.dts 文件的目录
MOD_DIR := ./mod

# build 目录
BUILD_DIR := ./build

# 几种扩展名的说明
# .pp.dts: 预处理后的 dts 文件，由源码 .dts, .dtsi 文件生成
# .pp.yaml: 由 .pp.dts 转换成的 YAML 文件
# .veriry：通过 .pp.yaml 验证 phandle_property_defines.csv 的结果
# .dtb: 由 .pp.dts 编译成的 dtb 文件。或者直接从某些设备中 dump 出来的 dtb 文件
# .rb.dts: 由 .dtb 反编译成的 dts 文件
# .rb.yaml: 由 .rb.dts 转换成的 YAML 文件
# .rb.p.yaml: 由 .rb.yaml 解析 phandle 路径后的 YAML 文件

# 从 kernel 源码中验证 phandle_property_defines.csv 的 .dts 文件列表
VERIFY_DTS_LIST := $(patsubst %,$(VERIFY_DTS_DIR)/%,$(VERIFY_DTS_NAME_LIST))
BUILD_VERIFY_DIR := $(BUILD_DIR)/verify
VERIFY_PP_DTS_LIST := $(patsubst %.dts,$(BUILD_VERIFY_DIR)/%.pp.dts,$(VERIFY_DTS_NAME_LIST))
VERIFY_PP_YAML_LIST := $(patsubst %.dts,$(BUILD_VERIFY_DIR)/%.pp.yaml,$(VERIFY_DTS_NAME_LIST))
VERIFY_RESULT_LIST := $(patsubst %.dts,$(BUILD_VERIFY_DIR)/%.verify,$(VERIFY_DTS_NAME_LIST))
VERIFY_DTB_LIST := $(patsubst %.dts,$(BUILD_VERIFY_DIR)/%.dtb,$(VERIFY_DTS_NAME_LIST))
VERIFY_RB_DTS_LIST := $(patsubst %.dts,$(BUILD_VERIFY_DIR)/%.rb.dts,$(VERIFY_DTS_NAME_LIST))
VERIFY_RB_YAML_LIST := $(patsubst %.dts,$(BUILD_VERIFY_DIR)/%.rb.yaml,$(VERIFY_DTS_NAME_LIST))
VERIFY_RB_P_YAML_LIST := $(patsubst %.dts,$(BUILD_VERIFY_DIR)/%.rb.p.yaml,$(VERIFY_DTS_NAME_LIST))

# dump 出来的 .dtb 文件列表
DUMP_DTB_LIST := $(wildcard $(DUMP_DIR)/*.dtb)
BUILD_DUMP_DIR := $(BUILD_DIR)/dump
DUMP_RB_DTS_LIST := $(patsubst $(DUMP_DIR)/%.dtb,$(BUILD_DUMP_DIR)/%.dts,$(DUMP_DTB_LIST))
DUMP_RB_YAML_LIST := $(patsubst $(DUMP_DIR)/%.dtb,$(BUILD_DUMP_DIR)/%.yaml,$(DUMP_DTB_LIST))
DUMP_RB_P_YAML_LIST := $(patsubst $(DUMP_DIR)/%.dtb,$(BUILD_DUMP_DIR)/%.p.yaml,$(DUMP_DTB_LIST))

# 魔改过的 .dts 文件列表
MOD_DTS_LIST := $(wildcard $(MOD_DIR)/*.dts)
BUILD_MOD_DIR := $(BUILD_DIR)/mod
MOD_YAML_LIST := $(patsubst $(MOD_DIR)/%.dts,$(BUILD_MOD_DIR)/%.yaml,$(MOD_DTS_LIST))
MOD_P_YAML_LIST := $(patsubst $(MOD_DIR)/%.dts,$(BUILD_MOD_DIR)/%.p.yaml,$(MOD_DTS_LIST))
MOD_RELEASE_LIST := $(patsubst $(MOD_DIR)/%.dts,$(BUILD_MOD_DIR)/%.dtb,$(MOD_DTS_LIST))

# 生成所有的文件
all: verify compare release

# 验证 phandle_property_defines.csv
verify: $(VERIFY_RESULT_LIST)

# 比较 .p.yaml 文件
compare: $(VERIFY_RB_P_YAML_LIST) $(DUMP_RB_P_YAML_LIST) $(MOD_P_YAML_LIST)

# 编译魔改的 dts 为 dtb
release: $(MOD_RELEASE_LIST)

clean:
	rm -rf $(BUILD_DIR)

.PHONY: all verify compare clean

# 使用 .SECONDARY 保护所有中间文件
.SECONDARY: \
	$(VERIFY_PP_DTS_LIST) \
	$(VERIFY_PP_YAML_LIST) \
	$(VERIFY_DTB_LIST) \
	$(VERIFY_RB_DTS_LIST) \
	$(VERIFY_RB_YAML_LIST) \
	$(DUMP_RB_DTS_LIST) \
	$(DUMP_RB_YAML_LIST) \
	$(MOD_YAML_LIST)

# dtsi 文件的 include 路径
CPP_INCLUDE := -I $(KERNEL_DIR)/include -I $(VERIFY_DTS_DIR)

# dts 预处理 include 的规则
$(BUILD_VERIFY_DIR)/%.pp.dts: $(VERIFY_DTS_DIR)/%.dts $(BUILD_VERIFY_DIR)
	cpp -nostdinc $(CPP_INCLUDE) -undef -x assembler-with-cpp $< -o $@

# dts 转换为 YAML 的规则
%.yaml: %.dts
	dtc -I dts -O yaml $< -o $@

# 特别的，对于 mod 目录中 dts 转换为 YAML 的规则
$(BUILD_MOD_DIR)/%.yaml: $(MOD_DIR)/%.dts $(BUILD_MOD_DIR)
	dtc -I dts -O yaml $< -o $@

# 验证 .pp.yaml 的规则
%.verify: %.pp.yaml
	python3 ./scripts/verify_phandle.py $< | tee $@

# .pp.dts 编译为 .dtb 的规则
%.dtb: %.pp.dts
	dtc -I dts -O dtb $< -o $@

# 特别的，对于魔改的 dts 编译为 dtb 的规则
$(BUILD_MOD_DIR)/%.dtb: $(MOD_DIR)/%.dts $(BUILD_MOD_DIR)
	dtc -I dts -O dtb $< -o $@

# dtb 反编译为 dts 的规则
%.rb.dts: %.dtb
	dtc -I dtb -s -O dts $< -o $@

# 特别的，对于 dump 出来的 dtb 反编译为 dts 的规则
$(BUILD_DUMP_DIR)/%.dts: $(DUMP_DIR)/%.dtb $(BUILD_DUMP_DIR)
	dtc -I dtb -s -O dts $< -o $@

# 给 YAML 文件解析 phandle 路径的规则
%.p.yaml: %.yaml
	python3 ./scripts/resolve_phandle.py $@ $<

# 创建目录规则
$(BUILD_VERIFY_DIR) $(BUILD_DUMP_DIR) $(BUILD_MOD_DIR):
	mkdir -p $@
