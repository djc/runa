declare i8* @malloc(i64)
declare void @free(i8*)
declare i64 @write(i32, i8*, i64)
declare i32 @asprintf(i8**, i8*, ...)
declare void @llvm.memcpy.p0i8.p0i8.i64(i8*, i8*, i64, i32, i1)

%IBool = type { i64 (i8*, i1*)* }
%IBool.wrap = type { %IBool*, i8* }

%str = type { i1, i64, i8* }
%IStr = type { i64 (i8*, %str*)* }
%IStr.wrap = type { %IStr*, i8* }

define i8* @lang.malloc(i64 %sz) alwaysinline {
	%1 = call i8* @malloc(i64 %sz)
	ret i8* %1
}

define void @lang.free(i8* %ptr) alwaysinline {
	call void @free(i8* %ptr)
	ret void
}
