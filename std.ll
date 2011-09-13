%struct.str = type { i64, i8* }

declare i64 @"\01_write"(i32, i8*, i64)

define void @print(%struct.str* %str) {
	%1 = getelementptr inbounds %struct.str* %str, i64 0, i32 1
	%2 = load i8** %1
	%3 = getelementptr inbounds %struct.str* %str, i64 0, i32 0
	%4 = load i64* %3
	tail call i64 @"\01_write"(i32 1, i8* %2, i64 %4)
	ret void
}
