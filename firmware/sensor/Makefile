# Builds with installed tools or explicit paths to a source build.
MICA_CC ?= mica-cc
MICA_AS ?= mica-as
MICA_LD ?= mica-ld
MICA_RUN ?= mica-run
BUILD_DIR ?= build
PROFILE = MICA-2E

.PHONY: all run
all: $(BUILD_DIR)/sensor.elf

$(BUILD_DIR):
	mkdir -p "$@"

$(BUILD_DIR)/sensor.o: ../../compiler/examples/sensor_node.c | $(BUILD_DIR)
	$(MICA_CC) --profile $(PROFILE) "$<" -o "$@"

$(BUILD_DIR)/platform.o: ../../compiler/examples/platform.c | $(BUILD_DIR)
	$(MICA_CC) --profile $(PROFILE) "$<" -o "$@"

$(BUILD_DIR)/startup.o: ../examples/sensor_start32.mica | $(BUILD_DIR)
	$(MICA_AS) --profile $(PROFILE) -c "$<" -o "$@"

$(BUILD_DIR)/sensor.elf: $(BUILD_DIR)/startup.o $(BUILD_DIR)/sensor.o $(BUILD_DIR)/platform.o
	$(MICA_LD) $^ --elf "$@" -o "$(BUILD_DIR)/sensor.bin"

run: $(BUILD_DIR)/sensor.elf
	$(MICA_RUN) --profile $(PROFILE) --watchdog --memory 65536 "$<"
