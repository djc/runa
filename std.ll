declare i8* @malloc(i64)
declare i64 @write(i32, i8*, i64)
declare i32 @asprintf(i8**, i8*, ...)

%struct.str = type { i64, i8* }
@str_NL = constant [1 x i8] c"\0a"
@fmt_INT = constant [2 x i8] c"%d"

define void @print(%struct.str* %str) {
	%s.data.ptr = getelementptr inbounds %struct.str* %str, i64 0, i32 1
	%s.data = load i8** %s.data.ptr
	%s.len.ptr = getelementptr inbounds %struct.str* %str, i64 0, i32 0
	%s.len = load i64* %s.len.ptr
	call i64 @write(i32 1, i8* %s.data, i64 %s.len)
	%nl.ptr = getelementptr inbounds [1 x i8]* @str_NL, i64 0, i64 0
	call i64 @write(i32 1, i8* %nl.ptr, i64 1)
	ret void
}

define %struct.str* @str(i64 %n) {
	%s.ptr.tmp = call i8* @malloc(i64 16)
	%s.ptr = bitcast i8* %s.ptr.tmp to %struct.str*
	%s.data = getelementptr %struct.str* %s.ptr, i32 0, i32 1
	%fmt = getelementptr inbounds [2 x i8]* @fmt_INT, i32 0, i32 0
	%fmt.len = call i32 (i8**, i8*, ...)* @asprintf(i8** %s.data, i8* %fmt, i64 %n)
	%fmt.len64 = sext i32 %fmt.len to i64
	%s.len = getelementptr inbounds %struct.str* %s.ptr, i32 0, i32 0
	store i64 %fmt.len64, i64* %s.len
	ret %struct.str* %s.ptr
}
