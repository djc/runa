declare i8* @malloc(i64)
declare void @free(i8*)
declare i64 @write(i32, i8*, i64)
declare i32 @asprintf(i8**, i8*, ...)
declare void @llvm.memcpy.p0i8.p0i8.i64(i8*, i8*, i64, i32, i1)

%IBool = type { void (i8*, i1*)* }
%IBool.wrap = type { %IBool*, i8* }

%str = type { i1, i64, i8* }
%IStr = type { void (i8*, %str*)* }
%IStr.wrap = type { %IStr*, i8* }
