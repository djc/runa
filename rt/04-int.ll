@fmt_INT = constant [4 x i8] c"%ld\00"

define void @int.__bool__(i64* %n.ptr, i1* %res) {
	%n = load i64* %n.ptr
	%1 = icmp ne i64 %n, 0
	store i1 %1, i1* %res
	ret void
}

define void @int.__str__(i64* %n.ptr, %str* %s) {
	%n = load i64* %n.ptr
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

define void @int.__eq__(i64* %a.ptr, i64* %b.ptr, i1* %res) {
	%a = load i64* %a.ptr
	%b = load i64* %b.ptr
	%1 = icmp eq i64 %a, %b
	store i1 %1, i1* %res
	ret void
}

define void @int.__lt__(i64* %a.ptr, i64* %b.ptr, i1* %res) {
	%a = load i64* %a.ptr
	%b = load i64* %b.ptr
	%1 = icmp slt i64 %a, %b
	store i1 %1, i1* %res
	ret void
}

define void @int.__add__(i64* %a.ptr, i64* %b.ptr, i64* %res) {
	%a = load i64* %a.ptr
	%b = load i64* %b.ptr
	%1 = add i64 %a, %b
	store i64 %1, i64* %res
	ret void
}

define void @int.__sub__(i64* %a.ptr, i64* %b.ptr, i64* %res) {
	%a = load i64* %a.ptr
	%b = load i64* %b.ptr
	%1 = sub i64 %a, %b
	store i64 %1, i64* %res
	ret void
}

define void @int.__mul__(i64* %a.ptr, i64* %b.ptr, i64* %res) {
	%a = load i64* %a.ptr
	%b = load i64* %b.ptr
	%1 = mul i64 %a, %b
	store i64 %1, i64* %res
	ret void
}

define void @int.__div__(i64* %a.ptr, i64* %b.ptr, i64* %res) {
	%a = load i64* %a.ptr
	%b = load i64* %b.ptr
	%1 = sdiv i64 %a, %b
	store i64 %1, i64* %res
	ret void
}

declare i32 @llvm.bswap.i32(i32)

define void @strtoi(%str* %s, i64* %res) {
	%len.ptr = getelementptr %str* %s, i32 0, i32 1
	%len = load i64* %len.ptr
	%data.ptr = getelementptr %str* %s, i32 0, i32 2
	%data = load i8** %data.ptr
	%num.ptr = bitcast i8* %data to i32*
	%num = load i32* %num.ptr
	%rev = call i32 @llvm.bswap.i32(i32 %num) ; ENDIAN
	%long = sext i32 %rev to i64
	store i64 %long, i64* %res
	ret void
}
