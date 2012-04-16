declare i32 @open(i8*, i32, ...)
declare i64 @read(i32, i8*, i64)
declare i32 @close(i32)

%file = type { i32 }

@file.READ = constant i32 0

define i64 @fopen(%str* %fn, %file* %f) {
	%path.ptr = getelementptr %str* %fn, i32 0, i32 2
	%path = load i8** %path.ptr
	%fd.ptr = getelementptr %file* %f, i32 0, i32 0
	%mode = load i32* @file.READ
	%fd = call i32 (i8*, i32, ...)* @open(i8* %path, i32 %mode)
	store i32 %fd, i32* %fd.ptr
	ret i64 0
}

define i64 @file.read(%file* %self, i64* %sz.ptr, %str* %res) {
	%sz = load i64* %sz.ptr
	%fd.ptr = getelementptr %file* %self, i32 0, i32 0
	%fd = load i32* %fd.ptr
	%data = call i8* @malloc(i64 %sz)
	%read = call i64 @read(i32 %fd, i8* %data, i64 %sz)
	%owner.ptr = getelementptr %str* %res, i32 0, i32 0
	store i1 true, i1* %owner.ptr
	%len.ptr = getelementptr %str* %res, i32 0, i32 1
	store i64 %read, i64* %len.ptr
	%data.ptr = getelementptr %str* %res, i32 0, i32 2
	store i8* %data, i8** %data.ptr
	ret i64 0
}

define i64 @file.close(%file* %self) {
	%fd.ptr = getelementptr %file* %self, i32 0, i32 0
	%fd = load i32* %fd.ptr
	call i32 @close(i32 %fd)
	ret i64 0
}
