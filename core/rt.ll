declare i8* @malloc(i64)
declare void @free(i8*)
declare i32 @printf(i8*, ...)

@fmt_MALLOC = constant [15 x i8] c"malloc(%ld) %p\0a"
@fmt_FREE = constant [9 x i8] c"free(%p)\0a"

define i8* @lang.malloc(i64 %sz) alwaysinline {
	%ptr = call i8* @malloc(i64 %sz)
	; %fmt = getelementptr inbounds [15 x i8]* @fmt_MALLOC, i32 0, i32 0
	; call i32 (i8*, ...)* @printf(i8* %fmt, i64 %sz, i8* %ptr)
	ret i8* %ptr
}

define void @lang.free(i8* %ptr) alwaysinline {
	; %fmt = getelementptr inbounds [9 x i8]* @fmt_FREE, i32 0, i32 0
	; call i32 (i8*, ...)* @printf(i8* %fmt, i8* %ptr)
	call void @free(i8* %ptr)
	ret void
}

define i8* @__ptr__.offset(i8* %base, i64 %offset) alwaysinline {
	%i = ptrtoint i8* %base to i64
	%new = add i64 %i, %offset
	%res = inttoptr i64 %new to i8*
	ret i8* %res
}
