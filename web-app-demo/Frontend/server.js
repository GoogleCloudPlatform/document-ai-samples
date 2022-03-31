var express = require('express');

var app = express();

const backendURL = process.env.BACKEND_URL;

app.use(express.static('dist/frontend'));

app.get('/', function (req, res,next) {
    console.log(process.env.BACKEND_URL);
    res.redirect('/');
});

app.listen(8080)