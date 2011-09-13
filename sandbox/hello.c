#include <unistd.h>

struct str {
	int len;
	char *data;
};

int myprint(struct str *data) {
	write(1, data->data, data->len);
	return 0;
}

int main(int argc, char** argv) {
	struct str x = {4, "test"};
	myprint(&x);
	return 0;
}
