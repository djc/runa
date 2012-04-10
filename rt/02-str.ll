declare i64 @strlen(i8*) nounwind readonly
declare i32 @strncmp(i8*, i8*, i64)

%str = type { i1, i64, i8* }
%IStr = type { void (i8*, %str*)* }
%IStr.wrap = type { %IStr*, i8* }

define void @str(%IStr.wrap* %if, %str* %res) {
	%vtable.ptr = getelementptr %IStr.wrap* %if, i32 0, i32 0
	%vtable = load %IStr** %vtable.ptr
	%fun.ptr = getelementptr %IStr* %vtable, i32 0, i32 0
	%fun = load void (i8*, %str*)** %fun.ptr
	%arg.ptr = getelementptr %IStr.wrap* %if, i32 0, i32 1
	%arg = load i8** %arg.ptr
	call void (i8*, %str*)* %fun(i8* %arg, %str* %res)
	ret void
}

@str_NL = constant [1 x i8] c"\0a"
@str.size = constant i64 ptrtoint (%str* getelementptr (%str* null, i32 1) to i64)

define void @str.__bool__(%str* %s, i1* %res) {
	%s.len = getelementptr %str* %s, i32 0, i32 1
	%len = load i64* %s.len
	%bool = icmp ne i64 %len, 0
	store i1 %bool, i1* %res
	ret void
}

define void @str.__eq__(%str* %a, %str* %b, i1* %res) {
	%a.len.ptr = getelementptr %str* %a, i32 0, i32 1
	%a.len = load i64* %a.len.ptr
	%b.len.ptr = getelementptr %str* %b, i32 0, i32 1
	%b.len = load i64* %b.len.ptr
	%samelen = icmp eq i64 %a.len, %b.len
	br i1 %samelen, label %Full, label %NEq
Full:
	%less = icmp slt i64 %a.len, %b.len
	%cmplen = select i1 %less, i64 %a.len, i64 %b.len
	%a.data.ptr = getelementptr %str* %a, i32 0, i32 2
	%b.data.ptr = getelementptr %str* %b, i32 0, i32 2
	%a.data = load i8** %a.data.ptr
	%b.data = load i8** %b.data.ptr
	%cmp = call i32 @strncmp(i8* %a.data, i8* %b.data, i64 %cmplen)
	%check = icmp eq i32 %cmp, 0
	store i1 %check, i1* %res
	ret void
NEq:
	store i1 false, i1* %res
	ret void
}

define void @str.__lt__(%str* %a, %str* %b, i1* %res) {
	%a.len.ptr = getelementptr %str* %a, i32 0, i32 1
	%a.len = load i64* %a.len.ptr
	%b.len.ptr = getelementptr %str* %b, i32 0, i32 1
	%b.len = load i64* %b.len.ptr
	%less = icmp slt i64 %a.len, %b.len
	%cmplen = select i1 %less, i64 %a.len, i64 %b.len
	%a.data.ptr = getelementptr %str* %a, i32 0, i32 2
	%b.data.ptr = getelementptr %str* %b, i32 0, i32 2
	%a.data = load i8** %a.data.ptr
	%b.data = load i8** %b.data.ptr
	%cmp = call i32 @strncmp(i8* %a.data, i8* %b.data, i64 %cmplen)
	%check = icmp slt i32 %cmp, 0
	br i1 %check, label %Less, label %EG
EG:
	%eq = icmp sgt i32 %cmp, 0
	br i1 %eq, label %NotLess, label %EQ
EQ:
	br i1 %less, label %Less, label %NotLess
Less:
	store i1 true, i1* %res
	ret void
NotLess:
	store i1 false, i1* %res
	ret void
}

define void @str.__add__(%str* %a, %str* %b, %str* %res) {
	%a.len.ptr = getelementptr %str* %a, i32 0, i32 1
	%a.len = load i64* %a.len.ptr
	%b.len.ptr = getelementptr %str* %b, i32 0, i32 1
	%b.len = load i64* %b.len.ptr
	%total = add i64 %a.len, %b.len
	%res.owner = getelementptr %str* %res, i32 0, i32 0
	store i1 true, i1* %res.owner
	%res.len.ptr = getelementptr %str* %res, i32 0, i32 1
	store i64 %total, i64* %res.len.ptr
	%res.data.ptr = getelementptr %str* %res, i32 0, i32 2
	%buf = call i8* @malloc(i64 %total)
	store i8* %buf, i8** %res.data.ptr
	%a.data.ptr = getelementptr %str* %a, i32 0, i32 2
	%a.data = load i8** %a.data.ptr
	call void @llvm.memcpy.p0i8.p0i8.i64(i8* %buf, i8* %a.data, i64 %a.len, i32 1, i1 false)
	%rest = getelementptr i8* %buf, i64 %a.len
	%b.data.ptr = getelementptr %str* %b, i32 0, i32 2
	%b.data = load i8** %b.data.ptr
	call void @llvm.memcpy.p0i8.p0i8.i64(i8* %rest, i8* %b.data, i64 %b.len, i32 1, i1 false)
	ret void
}

define void @str.__del__(%str* %s) {
	%owner.ptr = getelementptr %str* %s, i32 0, i32 0
	%owner = load i1* %owner.ptr
	br i1 %owner, label %Free, label %Done
Free:
	%data.ptr = getelementptr %str* %s, i32 0, i32 2
	%data = load i8** %data.ptr
	call void @free(i8* %data)
	br label %Done
Done:
	ret void
}

define void @wrapstr(i8* %s, %str* %out) {
	%out.owner = getelementptr %str* %out, i32 0, i32 0
	store i1 false, i1* %out.owner
	%s.len = getelementptr inbounds %str* %out, i32 0, i32 1
	%len = call i64 @strlen(i8* %s) nounwind readonly
	store i64 %len, i64* %s.len
	%s.data = getelementptr %str* %out, i32 0, i32 2
	store i8* %s, i8** %s.data
	ret void
}
