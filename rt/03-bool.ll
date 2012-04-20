@bool_TRUE = constant [4 x i8] c"True"
@bool_FALSE = constant [5 x i8] c"False"

define i64 @bool(%IBool.wrap* %if, i1* %res) {
	%vtable.ptr = getelementptr %IBool.wrap* %if, i32 0, i32 0
	%vtable = load %IBool** %vtable.ptr
	%fun.ptr = getelementptr %IBool* %vtable, i32 0, i32 0
	%fun = load i64 (i8*, i1*)** %fun.ptr
	%arg.ptr = getelementptr %IBool.wrap* %if, i32 0, i32 1
	%arg = load i8** %arg.ptr
	call i64 (i8*, i1*)* %fun(i8* %arg, i1* %res)
	ret i64 0
}

define i64 @bool.__str__(i1* %p, %str* %s) {
	%v = load i1* %p
	%s.owner = getelementptr %str* %s, i32 0, i32 0
	store i1 true, i1* %s.owner
	%s.data = getelementptr %str* %s, i32 0, i32 2
	%s.len = getelementptr inbounds %str* %s, i32 0, i32 1
	br i1 %v, label %True, label %False
True:
	store i64 4, i64* %s.len
	%ptr1 = call i8* @lang.malloc(i64 4)
	%val1 = getelementptr inbounds [4 x i8]* @bool_TRUE, i32 0, i32 0
	call void @llvm.memcpy.p0i8.p0i8.i64(i8* %ptr1, i8* %val1, i64 4, i32 1, i1 false)
	store i8* %ptr1, i8** %s.data
	br label %Done
False:
	store i64 5, i64* %s.len
	%ptr0 = call i8* @lang.malloc(i64 5)
	%val0 = getelementptr inbounds [5 x i8]* @bool_FALSE, i32 0, i32 0
	call void @llvm.memcpy.p0i8.p0i8.i64(i8* %ptr0, i8* %val0, i64 5, i32 1, i1 false)
	store i8* %ptr0, i8** %s.data
	br label %Done
Done:
	ret i64 0
}

@IStr.bool = constant %IStr { i64 (i8*, %str*)* bitcast ( i64 (i1*, %str*)* @bool.__str__ to i64 (i8*, %str*)*) }

define i64 @bool.__eq__(i1* %a.ptr, i1* %b.ptr, i1* %res) {
	%a = load i1* %a.ptr
	%b = load i1* %b.ptr
	%1 = xor i1 %a, %b
	%2 = select i1 %1, i1 false, i1 true
	store i1 %2, i1* %res
	ret i64 0
}
