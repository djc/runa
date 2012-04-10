@fmt_FLT = constant [3 x i8] c"%f\00"

define void @float.__str__(double* %n.ptr, %str* %s) {
	%n = load double* %n.ptr
	%s.owner = getelementptr %str* %s, i32 0, i32 0
	store i1 true, i1* %s.owner
	%s.data = getelementptr %str* %s, i32 0, i32 2
	%fmt = getelementptr inbounds [3 x i8]* @fmt_FLT, i32 0, i32 0
	%fmt.len = call i32 (i8**, i8*, ...)* @asprintf(i8** %s.data, i8* %fmt, double %n)
	%fmt.len64 = sext i32 %fmt.len to i64
	%s.len = getelementptr inbounds %str* %s, i32 0, i32 1
	store i64 %fmt.len64, i64* %s.len
	ret void
}

@IStr.float = constant %IStr { void (i8*, %str*)* bitcast ( void (double*, %str*)* @float.__str__ to void (i8*, %str*)*) }
