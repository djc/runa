declare i8* @malloc(i64)
declare void @free(i8*)
declare i64 @write(i32, i8*, i64)
declare i32 @asprintf(i8**, i8*, ...)
declare i32 @printf(i8*, ...)
declare void @llvm.memcpy.p0i8.p0i8.i64(i8*, i8*, i64, i32, i1)

%IBool = type { i64 (i8*, i1*)* }
%IBool.wrap = type { %IBool*, i8* }

%str = type { i1, i64, i8* }
%IStr = type { i64 (i8*, %str*)* }
%IStr.wrap = type { %IStr*, i8* }

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
