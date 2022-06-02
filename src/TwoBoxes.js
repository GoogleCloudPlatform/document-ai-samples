import React from 'react';
import Box from '@mui/material/Box';

class TwoBoxes extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      hilight: null
    };
  }

  render() {
    
    return (
        <Box sx={{width: "500px", height: "250px", backgroundColor: "yellow", display: "flex"}}>
          <Box sx={{backgroundColor: "red", width: "100px"}}>Box1</Box>
          <Box sx={{backgroundColor: "green", flexGrow: 1}}>Box2</Box>
        </Box>
    )
  }
}

export default TwoBoxes