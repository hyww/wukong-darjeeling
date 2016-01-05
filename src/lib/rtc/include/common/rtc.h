#ifndef RTC_H
#define RTC_H

#include "types.h"
#define RTC_COMPILED_CODE_BUFFER_SIZE 30000

void rtc_compile_lib(dj_infusion *);

#ifdef AVRORA
#define AVRORATRACE_DISABLE()    avroraTraceDisable();
#define AVRORATRACE_ENABLE()     avroraTraceEnable();
#else
#define AVRORATRACE_DISABLE()
#define AVRORATRACE_ENABLE()
#endif


uint16_t rtc_offset_for_static_ref(dj_infusion *infusion_ptr, uint8_t variable_index);
uint16_t rtc_offset_for_static_byte(dj_infusion *infusion_ptr, uint8_t variable_index);
uint16_t rtc_offset_for_static_short(dj_infusion *infusion_ptr, uint8_t variable_index);
uint16_t rtc_offset_for_static_int(dj_infusion *infusion_ptr, uint8_t variable_index);
uint16_t rtc_offset_for_static_long(dj_infusion *infusion_ptr, uint8_t variable_index);
uint16_t rtc_offset_for_referenced_infusion(dj_infusion *infusion_ptr, uint8_t ref_inf);
uint8_t offset_for_intlocal_short(dj_di_pointer methodimpl, uint8_t local);
uint8_t offset_for_intlocal_int(dj_di_pointer methodimpl, uint8_t local);
uint8_t offset_for_intlocal_long(dj_di_pointer methodimpl, uint8_t local);
uint8_t offset_for_reflocal(dj_di_pointer methodimpl, uint8_t local);

// Just a container for a lot of parameters we need to
// make available to rtc_translate_single_instruction
typedef struct _rtc_translationstate {
	dj_infusion *infusion;
	dj_di_pointer methodimpl;
    dj_di_pointer jvm_code_start;
    uint16_t pc;
    uint16_t method_length;
	dj_di_pointer branch_target_table_start_ptr;
	dj_di_pointer end_of_safe_region;
    uint16_t branch_target_count; // Keep track of how many branch targets we've seen
#ifdef AOT_OPTIMISE_CONSTANT_SHIFTS
    bool rtc_next_instruction_shifts_1_bit;
#endif // AOT_OPTIMISE_CONSTANT_SHIFTS
} rtc_translationstate;

#endif // RTC_H