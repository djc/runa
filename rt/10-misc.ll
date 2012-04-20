%array.str = type { i64, %str* }

define i64 @print(%IStr.wrap* %ss) {
	%s = alloca %str
	call i64 @str(%IStr.wrap* %ss, %str* %s)
	%s.data.ptr = getelementptr inbounds %str* %s, i64 0, i32 2
	%s.data = load i8** %s.data.ptr
	%s.len.ptr = getelementptr inbounds %str* %s, i64 0, i32 1
	%s.len = load i64* %s.len.ptr
	call i64 @write(i32 1, i8* %s.data, i64 %s.len)
	%nl.ptr = getelementptr inbounds [1 x i8]* @str_NL, i64 0, i64 0
	call i64 @write(i32 1, i8* %nl.ptr, i64 1)
	call i64 @str.__del__(%str* %s)
	ret i64 0
}

define i64 @argv(i32 %argc, i8** %argv, %array.str* %res) {
	
	%res.data = getelementptr %array.str* %res, i32 0, i32 1
	%num = sext i32 %argc to i64
	%str.size = load i64* @str.size
	%size = mul i64 %num, %str.size
	%array.raw = call i8* @lang.malloc(i64 %size)
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
		tail call i64 @wrapstr(i8* %arg, %str* %dst)
		%more = icmp sgt i64 %i, 0
		br i1 %more, label %Next, label %Done
	
	Done:
		%len.ptr = getelementptr %array.str* %res, i32 0, i32 0
		store i64 %num, i64* %len.ptr
		store %str* %array, %str** %res.data
		ret i64 0
	
}

%intiter = type { i64, i64, i64 }

define i64 @range(i64* %start.ptr, i64* %stop.ptr, i64* %step.ptr, %intiter* %res) {
	%1 = getelementptr inbounds %intiter* %res, i64 0, i32 0
	%start = load i64* %start.ptr
	store i64 %start, i64* %1
	%2 = getelementptr inbounds %intiter* %res, i64 0, i32 1
	%stop = load i64* %stop.ptr
	store i64 %stop, i64* %2
	%3 = getelementptr inbounds %intiter* %res, i64 0, i32 2
	%step = load i64* %step.ptr
	store i64 %step, i64* %3
	ret i64 0
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
