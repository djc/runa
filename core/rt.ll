declare void @exit(i32);
declare i8* @malloc({{ WORD }})
declare void @free(i8*)
declare void @llvm.memcpy.p0i8.p0i8.{{ WORD }}(i8*, i8*, {{ WORD }}, i32, i1)
declare {{ WORD }} @write(i32, i8*, {{ WORD }})

@fmt_MALLOC = constant [16 x i8] c"malloc(%ld) %p\0a\00"
@fmt_FREE = constant [10 x i8] c"free(%p)\0a\00"

define i8* @Runa.rt.malloc({{ WORD }} %sz) alwaysinline {
	%ptr = call i8* @malloc({{ WORD }} %sz)
	; %fmt = getelementptr inbounds [16 x i8]* @fmt_MALLOC, i32 0, i32 0
	; call i32 (i8*, ...)* @printf(i8* %fmt, {{ WORD }} %sz, i8* %ptr)
	ret i8* %ptr
}

define void @Runa.rt.free(i8* %ptr) alwaysinline {
	; %fmt = getelementptr inbounds [10 x i8]* @fmt_FREE, i32 0, i32 0
	; call i32 (i8*, ...)* @printf(i8* %fmt, i8* %ptr)
	call void @free(i8* %ptr)
	ret void
}

define i8* @Runa.rt.offset(i8* %base, {{ WORD }} %offset) alwaysinline {
	%i = ptrtoint i8* %base to {{ WORD }}
	%new = add {{ WORD }} %i, %offset
	%res = inttoptr {{ WORD }} %new to i8*
	ret i8* %res
}

define void @Runa.rt.memcpy(i8* %dst, i8* %src, {{ WORD }} %len) alwaysinline {
	call void @llvm.memcpy.p0i8.p0i8.{{ WORD }}(i8* %dst, i8* %src, {{ WORD }} %len, i32 1, i1 0)
	ret void
}

%Str = type { {{ WORD }}, i8* }
@Str.size = external constant {{ WORD }}
%array$Str = type { {{ WORD }}, [0 x %Str] }
declare void @Runa.core.Str.__init__$RStr.Obyte(%Str* %self, i8* %data) uwtable

define %array$Str* @Runa.rt.args(i32 %argc, i8** %argv) {
	
	%c64 = sext i32 %argc to {{ WORD }}
	%num = sub {{ WORD }} %c64, 1
	
	%str.size = load {{ WORD }}* @Str.size
	%arsz = mul {{ WORD }} %num, %str.size
	%objsz = add {{ WORD }} {{ BYTES }}, %arsz
	%array.raw = call i8* @Runa.rt.malloc({{ WORD }} %objsz)
	%array = bitcast i8* %array.raw to %array$Str*
	
	%array.data = getelementptr %array$Str* %array, i32 0, i32 1
	%array.len = getelementptr %array$Str* %array, i32 0, i32 0
	store {{ WORD }} %num, {{ WORD }}* %array.len
	
	%itervar = alloca {{ WORD }}
	store {{ WORD }} 0, {{ WORD }}* %itervar
	%first = icmp sgt {{ WORD }} %num, 0
	br i1 %first, label %Body, label %Done
	
Body:
	
	%idx = load {{ WORD }}* %itervar
	%orig.idx = add {{ WORD }} %idx, 1
	%arg.ptr = getelementptr inbounds i8** %argv, {{ WORD }} %orig.idx
	%arg = load i8** %arg.ptr
	
	%obj = getelementptr [0 x %Str]* %array.data, i32 0, {{ WORD }} %idx
	call void @Runa.core.Str.__init__$RStr.Obyte(%Str* %obj, i8* %arg)
	
	%next = add {{ WORD }} %idx, 1
	store {{ WORD }} %next, {{ WORD }}* %itervar
	%more = icmp slt {{ WORD }} %next, %num
	br i1 %more, label %Body, label %Done
	
Done:
	ret %array$Str* %array
	
}

%UnwEx = type { i64, i8*, i64, i64 }
%Exception = type { %UnwEx, i32, i8*, i8*, %Str* }
%UnwExClean = type void (i32, %UnwEx*)*

declare i32 @_Unwind_RaiseException(%UnwEx*)

@ExcErr = constant [44 x i8] c"!!! Runa: error while raising exception: %i\0a"
@ForeignExc = constant [35 x i8] c"!!! Runa: foreign exception caught\0a"
@Unhandled = constant [21 x i8] c"Unhandled Exception: "
@NL = constant [1 x i8] c"\0a"

define void @Runa.rt.unhandled(%Exception* %exc) {
	%prefix = getelementptr inbounds [21 x i8]* @Unhandled, i32 0, i32 0
	call {{ WORD }} @write(i32 2, i8* %prefix, {{ WORD }} 21)
	%msg.slot = getelementptr %Exception* %exc, i32 0, i32 4
	%msg = load %Str** %msg.slot
	%msg.data.slot = getelementptr %Str* %msg, i32 0, i32 1
	%msg.data = load i8** %msg.data.slot
	%msg.len.slot = getelementptr %Str* %msg, i32 0, i32 0
	%msg.len = load {{ WORD }}* %msg.len.slot
	call {{ WORD }} @write(i32 2, i8* %msg.data, {{ WORD }} %msg.len)
	%nl = getelementptr inbounds [1 x i8]* @NL, i32 0, i32 0
	call {{ WORD }} @write(i32 2, i8* %nl, {{ WORD }} 1)
	ret void
}

define void @Runa.rt.clean(i32 %reason, %UnwEx* %exc) {
	%cond = icmp eq i32 %reason, 1 ; _URC_FOREIGN_EXCEPTION_CAUGHT
	br i1 %cond, label %Foreign, label %Normal
Foreign:
	%msg = getelementptr inbounds [35 x i8]* @ForeignExc, i32 0, i32 0
	call {{ WORD }} @write(i32 2, i8* %msg, {{ WORD }} 35)
	call void @exit(i32 1)
	ret void
Normal:
	%bland = bitcast %UnwEx* %exc to i8*
	call void @free(i8* %bland)
	ret void
}

define void @Runa.rt.raise(%Exception* %obj) {
	%exc = bitcast %Exception* %obj to %UnwEx*
	%class = getelementptr %UnwEx* %exc, i32 0, i32 0
	store i64 19507889121949010, i64* %class ; 'RunaRNE\x00'
	%slot = getelementptr %UnwEx* %exc, i32 0, i32 1
	%clean = bitcast %UnwExClean @Runa.rt.clean to i8*
	store i8* %clean, i8** %slot
	%err = call i32 @_Unwind_RaiseException(%UnwEx* %exc)
	%cond = icmp eq i32 %err, 5 ; _URC_END_OF_STACK
	br i1 %cond, label %Unhandled, label %Other
Unhandled:
	call void @Runa.rt.unhandled(%Exception* %obj)
	br label %End
Other:
	%msg = getelementptr inbounds [44 x i8]* @ExcErr, i32 0, i32 0
	call {{ WORD }} @write(i32 2, i8* %msg, {{ WORD }} 44)
	br label %End
End:
	call void @exit(i32 1)
	ret void
}
