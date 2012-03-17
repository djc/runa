target triple = "x86_64-apple-darwin11.0.0"

declare i8* @malloc(i64)
declare i64 @write(i32, i8*, i64)
declare i32 @asprintf(i8**, i8*, ...)
declare i64 @strlen(i8*) nounwind readonly

%str = type { i64, i8* }
%intiter = type { i64, i64, i64 }
@str_NL = constant [1 x i8] c"\0a"
@fmt_INT = constant [4 x i8] c"%ld\00"

define void @print(%str* %s) {
	%s.data.ptr = getelementptr inbounds %str* %s, i64 0, i32 1
	%s.data = load i8** %s.data.ptr
	%s.len.ptr = getelementptr inbounds %str* %s, i64 0, i32 0
	%s.len = load i64* %s.len.ptr
	call i64 @write(i32 1, i8* %s.data, i64 %s.len)
	%nl.ptr = getelementptr inbounds [1 x i8]* @str_NL, i64 0, i64 0
	call i64 @write(i32 1, i8* %nl.ptr, i64 1)
	ret void
}

define void @str(i64 %n, %str* %s) {
	%s.data = getelementptr %str* %s, i32 0, i32 1
	%fmt = getelementptr inbounds [4 x i8]* @fmt_INT, i32 0, i32 0
	%fmt.len = call i32 (i8**, i8*, ...)* @asprintf(i8** %s.data, i8* %fmt, i64 %n)
	%fmt.len64 = sext i32 %fmt.len to i64
	%s.len = getelementptr inbounds %str* %s, i32 0, i32 0
	store i64 %fmt.len64, i64* %s.len
	ret void
}

define i1 @int.__bool__(i64 %n) {
	%1 = icmp ne i64 %n, 0
	ret i1 %1
}

define i1 @str.__bool__(%str* %s) {
	%s.len = getelementptr %str* %s, i32 0, i32 0
	%len = load i64* %s.len
	%res = icmp ne i64 %len, 0
	ret i1 %res
}

define void @wrapstr(i8* %s, %str* %out) {
	%s.len = getelementptr inbounds %str* %out, i32 0, i32 0
	%len = call i64 @strlen(i8* %s) nounwind readonly
	store i64 %len, i64* %s.len
	%s.data = getelementptr %str* %out, i32 0, i32 1
	store i8* %s, i8** %s.data
	ret void
}

define void @argv(i32 %argc, i8** %argv, %str** %out) {
	
	%num = sext i32 %argc to i64
	%size = mul i64 %num, 16
	%array.raw = call i8* @malloc(i64 %size)
	%array = bitcast i8* %array.raw to %str*
	%it.first = icmp sgt i64 %num, 0
	br i1 %it.first, label %Start, label %Done
	
	Start:
		br label %Next
	
	Next:
		%cur = phi i64 [ %num, %Start ], [ %i, %Next ]
		%i = add i64 %cur, -1
		%arg.ptr = getelementptr inbounds i8** %argv, i64 %i
		%arg = load i8** %arg.ptr
		%dst = getelementptr inbounds %str* %array, i64 %i
		tail call void @wrapstr(i8* %arg, %str* %dst)
		%more = icmp sgt i64 %i, 0
		br i1 %more, label %Next, label %Done
	
	Done:
		store %str* %array, %str** %out
		ret void
	
}

define void @range(i64 %start, i64 %stop, i64 %step, %intiter* %res) {
	%1 = getelementptr inbounds %intiter* %res, i64 0, i32 0
	store i64 %start, i64* %1
	%2 = getelementptr inbounds %intiter* %res, i64 0, i32 1
	store i64 %stop, i64* %2
	%3 = getelementptr inbounds %intiter* %res, i64 0, i32 2
	store i64 %step, i64* %3
	ret void
}

define i1 @intiter.__next__(%intiter* %self, i64* %res) {
	%start.ptr = getelementptr inbounds %intiter* %self, i64 0, i32 0
	%start = load i64* %start.ptr
	store i64 %start, i64* %res
	%step.ptr = getelementptr inbounds %intiter* %self, i64 0, i32 2
	%step = load i64* %step.ptr
	%next = add i64 %start, %step
	%stop.ptr = getelementptr inbounds %intiter* %self, i64 0, i32 1
	%stop = load i64* %stop.ptr
	%more = icmp sle i64 %next, %stop
	store i64 %next, i64* %start.ptr
	ret i1 %more
}
