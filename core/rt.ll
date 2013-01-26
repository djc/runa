declare i8* @malloc(i64)
declare void @free(i8*)
declare i32 @printf(i8*, ...)
declare void @llvm.memcpy.p0i8.p0i8.i64(i8*, i8*, i64, i32, i1)

@fmt_MALLOC = constant [16 x i8] c"malloc(%ld) %p\0a\00"
@fmt_FREE = constant [10 x i8] c"free(%p)\0a\00"

define i8* @runa.malloc(i64 %sz) alwaysinline {
	%ptr = call i8* @malloc(i64 %sz)
	; %fmt = getelementptr inbounds [16 x i8]* @fmt_MALLOC, i32 0, i32 0
	; call i32 (i8*, ...)* @printf(i8* %fmt, i64 %sz, i8* %ptr)
	ret i8* %ptr
}

define void @runa.free(i8* %ptr) alwaysinline {
	; %fmt = getelementptr inbounds [10 x i8]* @fmt_FREE, i32 0, i32 0
	; call i32 (i8*, ...)* @printf(i8* %fmt, i8* %ptr)
	call void @free(i8* %ptr)
	ret void
}

define i8* @runa.offset(i8* %base, i64 %offset) alwaysinline {
	%i = ptrtoint i8* %base to i64
	%new = add i64 %i, %offset
	%res = inttoptr i64 %new to i8*
	ret i8* %res
}

define void @runa.memcpy(i8* %dst, i8* %src, i64 %len) alwaysinline {
	call void @llvm.memcpy.p0i8.p0i8.i64(i8* %dst, i8* %src, i64 %len, i32 1, i1 0)
	ret void
}

%array$str = type { i64, [0 x %str] }

define %array$str* @args(i32 %argc, i8** %argv) {
	
	%c64 = sext i32 %argc to i64
	%num = sub i64 %c64, 1
	
	%str.size = load i64* @str.size
	%arsz = mul i64 %num, %str.size
	%objsz = add i64 8, %arsz
	%array.raw = call i8* @runa.malloc(i64 %objsz)
	%array = bitcast i8* %array.raw to %array$str*
	
	%array.data = getelementptr %array$str* %array, i32 0, i32 1
	%array.len = getelementptr %array$str* %array, i32 0, i32 0
	store i64 %num, i64* %array.len
	
	%itervar = alloca i64
	store i64 0, i64* %itervar
	%first = icmp sgt i64 %num, 0
	br i1 %first, label %Body, label %Done
	
Body:
	
	%idx = load i64* %itervar
	%orig.idx = add i64 %idx, 1
	%arg.ptr = getelementptr inbounds i8** %argv, i64 %orig.idx
	%arg = load i8** %arg.ptr
	
	%obj = getelementptr [0 x %str]* %array.data, i32 0, i64 %idx
	call void @str.__init__$Rstr.Obyte(%str* %obj, i8* %arg)
	
	%next = add i64 %idx, 1
	store i64 %next, i64* %itervar
	%more = icmp slt i64 %next, %num
	br i1 %more, label %Body, label %Done
	
Done:
	ret %array$str* %array
	
}
