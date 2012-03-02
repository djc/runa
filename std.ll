declare i8* @malloc(i64)
declare i64 @write(i32, i8*, i64)
declare i32 @asprintf(i8**, i8*, ...)
declare i64 @strlen(i8*) nounwind readonly

%struct.str = type { i64, i8* }
@str_NL = constant [1 x i8] c"\0a"
@fmt_INT = constant [4 x i8] c"%ld\00"

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
	%fmt = getelementptr inbounds [4 x i8]* @fmt_INT, i32 0, i32 0
	%fmt.len = call i32 (i8**, i8*, ...)* @asprintf(i8** %s.data, i8* %fmt, i64 %n)
	%fmt.len64 = sext i32 %fmt.len to i64
	%s.len = getelementptr inbounds %struct.str* %s.ptr, i32 0, i32 0
	store i64 %fmt.len64, i64* %s.len
	ret %struct.str* %s.ptr
}

define void @wrapstr(i8* %s, %struct.str* %out) {
	%s.len = getelementptr inbounds %struct.str* %out, i32 0, i32 0
	%len = call i64 @strlen(i8* %s) nounwind readonly
	store i64 %len, i64* %s.len
	%s.data = getelementptr %struct.str* %out, i32 0, i32 1
	store i8* %s, i8** %s.data
	ret void
}

define void @argv(i32 %argc, i8** %argv, %struct.str** %out) {
	
	%num = sext i32 %argc to i64
	%size = mul i64 %num, 16
	%array.raw = call i8* @malloc(i64 %size)
	%array = bitcast i8* %array.raw to %struct.str*
	%it.first = icmp sgt i64 %num, 0
	br i1 %it.first, label %Start, label %Done
	
	Start:
		br label %Next
	
	Next:
		%cur = phi i64 [ %num, %Start ], [ %i, %Next ]
		%i = add i64 %cur, -1
		%arg.ptr = getelementptr inbounds i8** %argv, i64 %i
		%arg = load i8** %arg.ptr
		%dst = getelementptr inbounds %struct.str* %array, i64 %i
		tail call void @wrapstr(i8* %arg, %struct.str* %dst)
		%more = icmp sgt i64 %i, 0
		br i1 %more, label %Next, label %Done
	
	Done:
		store %struct.str* %array, %struct.str** %out
		ret void
	
}

