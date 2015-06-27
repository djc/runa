// -*- C++ -*- The GNU C++ exception personality routine.
// Copyright (C) 2001-2015 Free Software Foundation, Inc.
//
// This file is part of GCC.
//
// GCC is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation; either version 3, or (at your option)
// any later version.
//
// GCC is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// Under Section 7 of GPL version 3, you are granted additional
// permissions described in the GCC Runtime Library Exception, version
// 3.1, as published by the Free Software Foundation.

// You should have received a copy of the GNU General Public License and
// a copy of the GCC Runtime Library Exception along with this program;
// see the files COPYING3 and COPYING.RUNTIME respectively.  If not, see
// <http://www.gnu.org/licenses/>.

// Cobbled together by djc from different files:
// * gcc/libstdc++-v3/libsupc++/eh_personality.cc
// * gcc/libgcc/unwind-pe.h
// ... and probably a few others?

#include <limits.h>
#include <stdint.h>
#include <stdbool.h>
#include <float.h>
#include <stdlib.h>
#include <stdio.h>

#include "unwind.h"

/*
 * Pointer encodings documented at:
 *   http://refspecs.freestandards.org/LSB_1.3.0/gLSB/gLSB/ehframehdr.html
 */

#define DW_EH_PE_omit      0xff  /* no data follows */

#define DW_EH_PE_absptr    0x00
#define DW_EH_PE_uleb128   0x01
#define DW_EH_PE_udata2    0x02
#define DW_EH_PE_udata4    0x03
#define DW_EH_PE_udata8    0x04
#define DW_EH_PE_sleb128   0x09
#define DW_EH_PE_sdata2    0x0A
#define DW_EH_PE_sdata4    0x0B
#define DW_EH_PE_sdata8    0x0C

#define DW_EH_PE_pcrel     0x10
#define DW_EH_PE_textrel   0x20
#define DW_EH_PE_datarel   0x30
#define DW_EH_PE_funcrel   0x40
#define DW_EH_PE_aligned   0x50
#define DW_EH_PE_indirect  0x80 /* gcc extension */

typedef unsigned _Unwind_Ptr __attribute__((__mode__(__pointer__)));
typedef unsigned _Unwind_Internal_Ptr __attribute__((__mode__(__pointer__)));
typedef unsigned _Unwind_Exception_Class __attribute__((__mode__(__DI__)));

#if __SIZEOF_LONG__ >= __SIZEOF_POINTER__
  typedef long _sleb128_t;
  typedef unsigned long _uleb128_t;
#elif __SIZEOF_LONG_LONG__ >= __SIZEOF_POINTER__
  typedef long long _sleb128_t;
  typedef unsigned long long _uleb128_t;
#else
# error "What type shall we use for _sleb128_t?"
#endif

static _Unwind_Ptr
base_of_encoded_value(unsigned char encoding, struct _Unwind_Context *context) {

  if (encoding == DW_EH_PE_omit)
    return 0;

  switch (encoding & 0x70) {
    case DW_EH_PE_absptr:
    case DW_EH_PE_pcrel:
    case DW_EH_PE_aligned:
      return 0;
// No support for textrel or datarel, apparently?
#if 0
    case DW_EH_PE_textrel:
      return _Unwind_GetTextRelBase(context);
    case DW_EH_PE_datarel:
      return _Unwind_GetDataRelBase(context);
#endif
    case DW_EH_PE_funcrel:
      return _Unwind_GetRegionStart(context);
  }
  abort();

}

static const unsigned char *
read_uleb128(const unsigned char *p, _uleb128_t *val) {

  unsigned int shift = 0;
  unsigned char byte;
  _uleb128_t result;

  result = 0;
  do {
    byte = *p++;
    result |= ((_uleb128_t)byte & 0x7f) << shift;
    shift += 7;
  } while (byte & 0x80);

  *val = result;
  return p;

}

static const unsigned char *
read_sleb128(const unsigned char *p, _sleb128_t *val) {

  unsigned int shift = 0;
  unsigned char byte;
  _uleb128_t result;

  result = 0;
  do {
    byte = *p++;
    result |= ((_uleb128_t)byte & 0x7f) << shift;
    shift += 7;
  } while (byte & 0x80);

  /* Sign-extend a negative value.  */
  if (shift < 8 * sizeof(result) && (byte & 0x40) != 0)
    result |= -(((_uleb128_t) 1L) << shift);

  *val = (_sleb128_t) result;
  return p;

}

static const unsigned char *
read_encoded_value_with_base(unsigned char encoding, _Unwind_Ptr base,
                             const unsigned char *p, _Unwind_Ptr *val) {

  union unaligned {
    void *ptr;
    unsigned u2 __attribute__ ((mode (HI)));
    unsigned u4 __attribute__ ((mode (SI)));
    unsigned u8 __attribute__ ((mode (DI)));
    signed s2 __attribute__ ((mode (HI)));
    signed s4 __attribute__ ((mode (SI)));
    signed s8 __attribute__ ((mode (DI)));
  } __attribute__((__packed__));

  const union unaligned *u = (const union unaligned *) p;
  _Unwind_Internal_Ptr result;

  if (encoding == DW_EH_PE_aligned) {
    _Unwind_Internal_Ptr a = (_Unwind_Internal_Ptr) p;
    a = (a + sizeof (void *) - 1) & - sizeof(void *);
    result = *(_Unwind_Internal_Ptr *) a;
    p = (const unsigned char *) (_Unwind_Internal_Ptr) (a + sizeof (void *));
  } else {

    switch (encoding & 0x0f) {

      case DW_EH_PE_absptr:
        result = (_Unwind_Internal_Ptr) u->ptr;
        p += sizeof (void *);
        break;

      case DW_EH_PE_uleb128: {
          _uleb128_t tmp;
          p = read_uleb128(p, &tmp);
          result = (_Unwind_Internal_Ptr) tmp;
        }
        break;

      case DW_EH_PE_sleb128: {
          _sleb128_t tmp;
          p = read_sleb128 (p, &tmp);
          result = (_Unwind_Internal_Ptr) tmp;
        }
        break;

      case DW_EH_PE_udata2:
        result = u->u2;
        p += 2;
        break;
      case DW_EH_PE_udata4:
        result = u->u4;
        p += 4;
        break;
      case DW_EH_PE_udata8:
        result = u->u8;
        p += 8;
        break;

      case DW_EH_PE_sdata2:
        result = u->s2;
        p += 2;
        break;
      case DW_EH_PE_sdata4:
        result = u->s4;
        p += 4;
        break;
      case DW_EH_PE_sdata8:
        result = u->s8;
        p += 8;
        break;

      default:
        abort();

    }

    if (result != 0) {
      result += ((encoding & 0x70) == DW_EH_PE_pcrel ? (_Unwind_Internal_Ptr) u : base);
      if (encoding & DW_EH_PE_indirect)
        result = *(_Unwind_Internal_Ptr*) result;
    }

  }

  *val = result;
  return p;

}

static inline const unsigned char *
read_encoded_value(struct _Unwind_Context *context, unsigned char encoding,
                   const unsigned char *p, _Unwind_Ptr *val) {
  return read_encoded_value_with_base(encoding,
           base_of_encoded_value(encoding, context), p, val);
}

/* read a uleb128 encoded value and advance pointer */
static uintptr_t readULEB128(const uint8_t** data) {
    uintptr_t result = 0;
    uintptr_t shift = 0;
    unsigned char byte;
    const uint8_t* p = *data;
    do {
        byte = *p++;
        result |= (byte & 0x7f) << shift;
        shift += 7;
    } while (byte & 0x80);
    *data = p;
    return result;
}

/* read a pointer encoded value and advance pointer */
static uintptr_t readEncodedPointer(const uint8_t** data, uint8_t encoding) {

    const uint8_t* p = *data;
    uintptr_t result = 0;

    if (encoding == DW_EH_PE_omit)
        return 0;

    /* first get value */
    switch (encoding & 0x0F) {
        case DW_EH_PE_absptr:
            result = *((const uintptr_t*) p);
            p += sizeof(uintptr_t);
            break;
        case DW_EH_PE_uleb128:
            result = readULEB128(&p);
            break;
        case DW_EH_PE_udata2:
            result = *((const uint16_t*) p);
            p += sizeof(uint16_t);
            break;
        case DW_EH_PE_udata4:
            result = *((const uint32_t*) p);
            p += sizeof(uint32_t);
            break;
        case DW_EH_PE_udata8:
            result = *((const uint64_t*) p);
            p += sizeof(uint64_t);
            break;
        case DW_EH_PE_sdata2:
            result = *((const int16_t*) p);
            p += sizeof(int16_t);
            break;
        case DW_EH_PE_sdata4:
            result = *((const int32_t*) p);
            p += sizeof(int32_t);
            break;
        case DW_EH_PE_sdata8:
            result = *((const int64_t*) p);
            p += sizeof(int64_t);
            break;
        case DW_EH_PE_sleb128:
        default:
            /* not supported */
            abort();
            break;
    }

    /* then add relative offset */
    switch (encoding & 0x70) {
        case DW_EH_PE_absptr:
            /* do nothing */
            break;
        case DW_EH_PE_pcrel:
            result += (uintptr_t)(*data);
            break;
        case DW_EH_PE_textrel:
        case DW_EH_PE_datarel:
        case DW_EH_PE_funcrel:
        case DW_EH_PE_aligned:
        default:
            /* not supported */
            abort();
            break;
    }

    /* then apply indirection */
    if (encoding & DW_EH_PE_indirect) {
        result = *((const uintptr_t*) result);
    }

    *data = p;
    return result;
}

struct lsda_header_info {
  _Unwind_Ptr Start;
  _Unwind_Ptr LPStart;
  _Unwind_Ptr ttype_base;
  const unsigned char *TType;
  const unsigned char *action_table;
  unsigned char ttype_encoding;
  unsigned char call_site_encoding;
};

static const unsigned char *
parse_lsda_header(struct _Unwind_Context *context, const unsigned char *p,
                  struct lsda_header_info *info) {

    _uleb128_t tmp;
    unsigned char lpstart_encoding;
    info->Start = (context ? _Unwind_GetRegionStart(context) : 0);

    // Find @LPStart, the base to which landing pad offsets are relative.
    lpstart_encoding = *p++;
    if (lpstart_encoding != DW_EH_PE_omit)
        p = read_encoded_value(context, lpstart_encoding, p, &info->LPStart);
    else
        info->LPStart = info->Start;

    // Find @TType, the base of the handler and exception spec type data.
    info->ttype_encoding = *p++;
    if (info->ttype_encoding != DW_EH_PE_omit) {
        p = read_uleb128 (p, &tmp);
        info->TType = p + tmp;
    } else {
        info->TType = 0;
    }

    // The encoding and length of the call-site table; the action table
    // immediately follows.
    info->call_site_encoding = *p++;
    p = read_uleb128 (p, &tmp);
    info->action_table = p + tmp;

    return p;

}

// Runa-specific parts start here!

// Keep in sync with Exception class in core/eh.rns
struct RunaException {
  struct _Unwind_Exception header;
  int switch_value;
  const unsigned char* lsda;
  _Unwind_Ptr lpad;
};

static inline void save_caught_exception(struct _Unwind_Exception* ue_header,
    int handler_switch_value, const unsigned char* lsda, _Unwind_Ptr landing_pad) {
  struct RunaException* exc = (struct RunaException*) ue_header;
  exc->switch_value = handler_switch_value;
  exc->lsda = lsda;
  exc->lpad = landing_pad;
}

static inline void restore_caught_exception(struct _Unwind_Exception* ue_header,
    int* handler_switch_value, const unsigned char** lsda, _Unwind_Ptr* landing_pad) {
  struct RunaException* exc = (struct RunaException*) ue_header;
  *handler_switch_value = exc->switch_value;
  *lsda = exc->lsda;
  *landing_pad = exc->lpad;
}

#define RUNA_CLASS 19507889121949010

_Unwind_Reason_Code __runa_personality(int version,
  _Unwind_Action actions, _Unwind_Exception_Class exception_class,
  struct _Unwind_Exception *ue_header, struct _Unwind_Context *context) {

  enum found_handler_type {
    found_nothing, found_terminate, found_cleanup, found_handler
  } found_type;

  struct lsda_header_info info;
  const unsigned char *language_specific_data;
  const unsigned char *action_record;
  const unsigned char *p;
  _Unwind_Ptr landing_pad, ip;
  int handler_switch_value;
  void* thrown_ptr = 0;
  bool foreign_exception;
  int ip_before_insn = 0;

  //__cxa_exception* xh = __get_exception_header_from_ue(ue_header);

  // Interface version check.
  if (version != 1)
    return _URC_FATAL_PHASE1_ERROR;

  foreign_exception = exception_class != RUNA_CLASS;

  // Shortcut for phase 2 found handler for domestic exception.
  if (actions == (_UA_CLEANUP_PHASE | _UA_HANDLER_FRAME) && !foreign_exception) {
    restore_caught_exception(ue_header, &handler_switch_value,
                             &language_specific_data, &landing_pad);
    found_type = (landing_pad == 0 ? found_terminate : found_handler);
    goto install_context;
  }

  language_specific_data = (const unsigned char *) _Unwind_GetLanguageSpecificData(context);

  // If no LSDA, then there are no handlers or cleanups.
  if (!language_specific_data)
    return _URC_CONTINUE_UNWIND;

  // Parse the LSDA header.
  p = parse_lsda_header(context, language_specific_data, &info);
  info.ttype_base = base_of_encoded_value(info.ttype_encoding, context);
  ip = _Unwind_GetIPInfo(context, &ip_before_insn);
  //ip = _Unwind_GetIP(context);
  if (!ip_before_insn)
    --ip;

  landing_pad = 0;
  action_record = 0;
  handler_switch_value = 0;

  // Search the call-site table for the action associated with this IP.
  while (p < info.action_table) {

    _Unwind_Ptr cs_start, cs_len, cs_lp;
    _uleb128_t cs_action;

    // Note that all call-site encodings are "absolute" displacements.
    p = read_encoded_value(0, info.call_site_encoding, p, &cs_start);
    p = read_encoded_value(0, info.call_site_encoding, p, &cs_len);
    p = read_encoded_value(0, info.call_site_encoding, p, &cs_lp);
    p = read_uleb128(p, &cs_action);

    // The table is sorted, so if we've passed the ip, stop.
    if (ip < info.Start + cs_start) {
      p = info.action_table;
    } else if (ip < info.Start + cs_start + cs_len) {
      if (cs_lp)
        landing_pad = info.LPStart + cs_lp;
      if (cs_action)
        action_record = info.action_table + cs_action - 1;
      goto found_something;
    }

  }

  // If ip is not present in the table, call terminate. This is for
  // a destructor inside a cleanup, or a library routine the compiler
  // was not expecting to throw.
  found_type = found_terminate;
  goto do_something;

 found_something:
  if (landing_pad == 0) {
    // If ip is present, and has a null landing pad, there are
    // no cleanups or handlers to be run.
    found_type = found_nothing;
  } else if (action_record == 0) {
    // If ip is present, has a non-null landing pad, and a null
    // action table offset, then there are only cleanups present.
    // Cleanups use a zero switch value, as set above.
    found_type = found_cleanup;
  } else {

    // Otherwise we have a catch handler or exception specification.
    _sleb128_t ar_filter, ar_disp;
    //const std::type_info* catch_type;
    //_throw_typet* throw_type;
    bool saw_cleanup = false;
    bool saw_handler = false;

    {
      //thrown_ptr = __get_object_from_ue(ue_header);
      //throw_type = __get_exception_header_from_obj(thrown_ptr)->exceptionType;
    }

    while (1) {

      p = action_record;
      p = read_sleb128(p, &ar_filter);
      read_sleb128(p, &ar_disp);

      if (ar_filter == 0) {
        // Zero filter values are cleanups.
        saw_cleanup = true;
      } else if (ar_filter > 0) {

        // Positive filter values are handlers.
        //catch_type = get_ttype_entry(&info, ar_filter);
        //printf("positive filter value -- handler found\n");
        saw_handler = true;
        break;

        // Null catch type is a catch-all handler; we can catch foreign
        // exceptions with this. Otherwise we must match types.

        //if (!catch_type || (throw_type &&
        //                    get_adjusted_ptr(catch_type, throw_type, &thrown_ptr))) {
        //  saw_handler = true;
        //  break;
        //}

      } else {

        printf("negative filter value -- exception spec\n");
        // Negative filter values are exception specifications.
        // ??? How do foreign exceptions fit in?  As far as I can
        // see we can't match because there's no __cxa_exception
        // object to stuff bits in for __cxa_call_unexpected to use.
        // Allow them iff the exception spec is non-empty.  I.e.
        // a throw() specification results in __unexpected.

        //if ((throw_type && !(actions & _UA_FORCE_UNWIND) && !foreign_exception) ?
        //    !check_exception_spec(&info, throw_type, thrown_ptr, ar_filter) :
        //    empty_exception_spec(&info, ar_filter)) {
        //  saw_handler = true;
        //  break;
        //}

      }

      if (ar_disp == 0)
        break;
      action_record = p + ar_disp;

    }

    if (saw_handler) {
      handler_switch_value = ar_filter;
      found_type = found_handler;
    } else {
      found_type = (saw_cleanup ? found_cleanup : found_nothing);
    }

  }

 do_something:

   if (found_type == found_nothing)
     return _URC_CONTINUE_UNWIND;

  if (actions & _UA_SEARCH_PHASE) {

    if (found_type == found_cleanup)
      return _URC_CONTINUE_UNWIND;

    // For domestic exceptions, we cache data from phase 1 for phase 2.
    if (!foreign_exception) {
      save_caught_exception(ue_header, handler_switch_value,
                            language_specific_data, landing_pad);
    }

    return _URC_HANDLER_FOUND;
  }

 install_context:

  // We can't use any of the cxa routines with foreign exceptions,
  // because they all expect ue_header to be a struct __cxa_exception.
  // So in that case, call terminate or unexpected directly.
  if ((actions & _UA_FORCE_UNWIND) || foreign_exception) {

    if (found_type == found_terminate)
      abort(); // std::terminate();
    else if (handler_switch_value < 0) {
      printf("WTF\n");
      //__try
      //  { std::unexpected (); }
      //__catch(...)
      //  { std::terminate (); }
    }

  } else {

    if (found_type == found_terminate)
      abort(); //__cxa_call_terminate(ue_header);

    // Cache the TType base value for __cxa_call_unexpected, as we won't
    // have an _Unwind_Context then.
    if (handler_switch_value < 0) {
      parse_lsda_header(context, language_specific_data, &info);
      info.ttype_base = base_of_encoded_value(info.ttype_encoding, context);
      //xh->catchTemp = base_of_encoded_value (info.ttype_encoding, context);
    }

  }

  /* For targets with pointers smaller than the word size, we must extend the
     pointer, and this extension is target dependent.  */
  _Unwind_SetGR(context, __builtin_eh_return_data_regno(0), __builtin_extend_pointer(ue_header));
  _Unwind_SetGR(context, __builtin_eh_return_data_regno(1), handler_switch_value);
  _Unwind_SetIP(context, landing_pad);
  return _URC_INSTALL_CONTEXT;

}
