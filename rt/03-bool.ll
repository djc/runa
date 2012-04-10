@bool_TRUE = constant [4 x i8] c"True"
@bool_FALSE = constant [5 x i8] c"False"

define void @bool.__str__(i1* %p, %str* %s) {
	%v = load i1* %p
	%s.owner = getelementptr %str* %s, i32 0, i32 0
	store i1 true, i1* %s.owner
	%s.data = getelementptr %str* %s, i32 0, i32 2
	%s.len = getelementptr inbounds %str* %s, i32 0, i32 1
	br i1 %v, label %True, label %False
True:
	store i64 4, i64* %s.len
	%ptr1 = call i8* @malloc(i64 4)
	%val1 = getelementptr inbounds [4 x i8]* @bool_TRUE, i32 0, i32 0
	call void @llvm.memcpy.p0i8.p0i8.i64(i8* %ptr1, i8* %val1, i64 4, i32 1, i1 false)
	store i8* %ptr1, i8** %s.data
	br label %Done
False:
	store i64 5, i64* %s.len
	%ptr0 = call i8* @malloc(i64 5)
	%val0 = getelementptr inbounds [5 x i8]* @bool_FALSE, i32 0, i32 0
	call void @llvm.memcpy.p0i8.p0i8.i64(i8* %ptr0, i8* %val0, i64 5, i32 1, i1 false)
	store i8* %ptr0, i8** %s.data
	br label %Done
Done:
	ret void
}

@IStr.bool = constant %IStr { void (i8*, %str*)* bitcast ( void (i1*, %str*)* @bool.__str__ to void (i8*, %str*)*) }

define void @bool.__eq__(i1* %a.ptr, i1* %b.ptr, i1* %res) {
	%a = load i1* %a.ptr
	%b = load i1* %b.ptr
	%1 = xor i1 %a, %b
	%2 = select i1 %1, i1 false, i1 true
	store i1 %2, i1* %res
	ret void
}
