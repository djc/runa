@fmt_INT = constant [4 x i8] c"%ld\00"

define void @int.__bool__(i64 %n, i1* %res) {
	%1 = icmp ne i64 %n, 0
	store i1 %1, i1* %res
	ret void
}

define void @int.__str__(i64 %n, %str* %s) {
	%s.owner = getelementptr %str* %s, i32 0, i32 0
	store i1 true, i1* %s.owner
	%s.data = getelementptr %str* %s, i32 0, i32 2
	%fmt = getelementptr inbounds [4 x i8]* @fmt_INT, i32 0, i32 0
	%fmt.len = call i32 (i8**, i8*, ...)* @asprintf(i8** %s.data, i8* %fmt, i64 %n)
	%fmt.len64 = sext i32 %fmt.len to i64
	%s.len = getelementptr inbounds %str* %s, i32 0, i32 1
	store i64 %fmt.len64, i64* %s.len
	ret void
}

define void @int.__eq__(i64 %a, i64 %b, i1* %res) {
	%1 = icmp eq i64 %a, %b
	store i1 %1, i1* %res
	ret void
}

define void @int.__lt__(i64 %a, i64 %b, i1* %res) {
	%1 = icmp slt i64 %a, %b
	store i1 %1, i1* %res
	ret void
}

define void @int.__add__(i64 %a, i64 %b, i64* %res) {
	%1 = add i64 %a, %b
	store i64 %1, i64* %res
	ret void
}

define void @int.__sub__(i64 %a, i64 %b, i64* %res) {
	%1 = sub i64 %a, %b
	store i64 %1, i64* %res
	ret void
}

define void @int.__mul__(i64 %a, i64 %b, i64* %res) {
	%1 = mul i64 %a, %b
	store i64 %1, i64* %res
	ret void
}

define void @int.__div__(i64 %a, i64 %b, i64* %res) {
	%1 = sdiv i64 %a, %b
	store i64 %1, i64* %res
	ret void
}

@zero = constant i64 0

define void @strtoi(%str* %s, i64* %res) {
	%len.ptr = getelementptr %str* %s, i32 0, i32 1
	%len = load i64* %len.ptr
	%data.ptr = getelementptr %str* %s, i32 0, i32 2
	%data = load i8** %data.ptr
	%start = load i64* @zero
	%count = load i64* %len.ptr
	br label %Start
Start:
	br label %Next
Next:
	%cur = phi i64 [ %len, %Start ], [ %i, %Next ]
	%val = phi i64 [ %start, %Start ], [ %add, %Next ]
	%i = add i64 %cur, -1
	%char.ptr = getelementptr i8* %data, i64 %i
	%char = load i8* %char.ptr
	%long = sext i8 %char to i64
	%rev1 = sub i64 %len, %i
	%rev0 = sub i64 %rev1, 1
	%shift = mul i64 %rev0, 8
	%new = shl i64 %long, %shift
	%add = add i64 %val, %new
	%more = icmp sgt i64 %i, 0
	br i1 %more, label %Next, label %Done
Done:
	store i64 %add, i64* %res
	ret void
}
