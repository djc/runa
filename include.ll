%str = type { i64, i8* }

declare void @print(%str* %s)
declare void @str(i64 %n, %str* %s)
declare i1 @int.__bool__(i64 %n)
declare i1 @str.__bool__(%str* %s)
declare void @argv(i32 %argc, i8** %argv, %str** %out)
