%struct.str = type { i64, i8* }
@str_NL = constant [1 x i8] c"\0a"
declare i64 @"\01_write"(i32, i8*, i64)

define void @print(%struct.str* %str) {
	%1 = getelementptr inbounds %struct.str* %str, i64 0, i32 1
	%2 = load i8** %1
	%3 = getelementptr inbounds %struct.str* %str, i64 0, i32 0
	%4 = load i64* %3
	call i64 @"\01_write"(i32 1, i8* %2, i64 %4)
	%6 = getelementptr inbounds [1 x i8]* @str_NL, i64 0, i64 0
	call i64 @"\01_write"(i32 1, i8* %6, i64 1)
	ret void
}
